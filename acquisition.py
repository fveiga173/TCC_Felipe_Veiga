"""Aquisições com segmentos explícitos e conversão em blocos de memória limitada."""
from dataclasses import dataclass, field
import hashlib
import io
import re
import zlib
import numpy as np
import pandas as pd
from psd_recipe import parse_metadata


@dataclass
class Recording:
    raw: np.ndarray
    fs: float
    scale: float
    segments: pd.DataFrame
    metadata: dict = field(default_factory=dict)
    notices: list = field(default_factory=list)

    def values(self, first, end):
        return self.raw[int(first):int(end)].astype(np.float64)/self.scale

    @property
    def samples(self):
        return int(self.segments.end_sample_exclusive.iloc[-1])

    @property
    def exposure_s(self):
        return float((self.segments.end_sample_exclusive-self.segments.first_sample).sum()/self.fs)


def _configuration(m):
    fs, scale = float(m['sample_rate_nominal_hz']), float(m['lsb_per_g'])
    legacy = fs == 500 and m.get('dlpf_cfg') == '2' and m.get('who_am_i') in (None, '104', '0x68')
    modern = (fs == 1000 and m.get('who_am_i') in ('112', '0x70') and
              m.get('sample_rate_divider') == '0' and m.get('gyro_dlpf_cfg') == '1' and
              m.get('accel_dlpf_cfg') == '0' and m.get('gyro_fchoice_b') == '0')
    if not (legacy or modern) or scale != 8192 or int(m['accel_range_g']) != 4:
        raise ValueError('Configuração não suportada: conferir identificação, filtros, divisor e escala no TXT.')
    return fs, scale


def read_binary(binary, report):
    """V1 exige fechamento OK; V2 aceita somente prefixos com CRC e limites verificados.

    Não cria um vetor de tempo nem converte o BIN inteiro para float. Um V2
    incompleto pode conter cauda sem checkpoint; a cauda permanece fora da análise.
    """
    report_bytes = report if isinstance(report, bytes) else report.encode('utf-8')
    if isinstance(report, bytes): report = report.decode('utf-8-sig')
    m = parse_metadata(report)
    try: fs, scale = _configuration(m)
    except (KeyError, TypeError, ValueError) as exc: raise ValueError(f'TXT de aquisição inválido: {exc}') from exc
    data = memoryview(binary)
    rows, notices = [], []
    fmt = m.get('format')
    if fmt == 'MPUZ_RAW_LE_V1':
        if m.get('time_basis') != 'sample_index_nominal' or m.get('status') != 'OK':
            raise ValueError('V1 requer fechamento OK: não contém limites para recuperar trechos após falhas.')
        if int(m.get('error_code', -1)) or int(m.get('fifo_overflows', -1)):
            raise ValueError('Falha/overflow no V1; não há segmentação para assegurar continuidade.')
        n = int(m.get('samples', 0))
        if n < 16 or len(data) != 2*n or zlib.crc32(data) != int(m.get('crc32', -1)):
            raise ValueError('BIN e TXT divergentes: quantidade ou CRC32 incorreto.')
        rows = [dict(segment_id=1, first_sample=0, end_sample_exclusive=n,
                     start_arduino_ms=0, stop_arduino_ms=int(m.get('duration_arduino_ms', 0)),
                     reason=1, crc32_prefix=int(m['crc32']))]
        closed = True
    elif fmt == 'MPUZ_RAW_LE_V2':
        if m.get('time_basis') != 'sample_index_nominal_per_segment':
            raise ValueError('V2 exige base nominal por segmento.')
        segments = {}
        for line in report.splitlines():
            line = re.sub(r'^\s*\d{2}:\d{2}:\d{2}\.\d+\s*->\s*', '', line).strip()
            if not line.startswith('segment='): continue
            try:
                row = tuple(map(int, line.split('=', 1)[1].split(',')))
                if len(row) != 7 or min(row) < 0: raise ValueError()
            except ValueError:
                notices.append('Linha de segmento parcial ignorada; somente registros completos foram conferidos.')
                continue
            if row[0] in segments and segments[row[0]] != row:
                notices.append(f'Segmento {row[0]} repetido com conteúdo diferente: adotado o último registro completo, sujeito à conferência de limites e CRC.')
            segments[row[0]] = row
        if not segments: raise ValueError('V2 sem segmento completo para conferir.')
        previous_end, previous_stop, crc, position = 0, 0, 0, 0
        for ident in sorted(segments):
            ident, first, end, start, stop, reason, checksum = segments[ident]
            if first != previous_end or end < first or 2*end > len(data) or start < previous_stop or stop < start:
                raise ValueError('Limites de segmentos inválidos, sobrepostos ou fora do BIN.')
            target = 2*end
            while position < target:
                next_position = min(target, position+1024*1024)
                crc = zlib.crc32(data[position:next_position], crc)
                position = next_position
            if crc != checksum: raise ValueError(f'CRC32 divergente no segmento {ident}; análise bloqueada.')
            rows.append(dict(segment_id=ident, first_sample=first, end_sample_exclusive=end,
                             start_arduino_ms=start, stop_arduino_ms=stop, reason=reason, crc32_prefix=checksum))
            previous_end, previous_stop = end, stop
        n = previous_end
        closed = m.get('session_closed') == '1'
        if closed:
            if len(data) != 2*n or int(m.get('samples', -1)) != n or int(m.get('crc32', -1)) != crc:
                raise ValueError('Fechamento V2 divergente do tamanho/CRC final.')
        else:
            notices.append('Sessão sem fechamento final: análise limitada aos segmentos com CRC verificado.')
        tail = len(data)-2*n
        if tail: notices.append(f'Cauda de {tail} bytes sem segmento confirmado excluída da análise.')
        if m.get('status') == 'REVIEW' or int(m.get('fifo_overflows', m.get('fifo_overflows_so_far', 0))):
            notices.append('A aquisição registra falhas recuperadas. As fronteiras permanecem separadas na PSD.')
    else:
        raise ValueError('Formato BIN/TXT não reconhecido.')
    if n < 16: raise ValueError('Não há amostras verificadas suficientes.')
    raw = np.frombuffer(data[:2*n], dtype='<i2')
    rails = sum(int(np.count_nonzero((b == -32768) | (b == 32767))) for b in
                (raw[i:i+1000000] for i in range(0, n, 1000000)))
    m = dict(m, integrity_verified=True, verified_samples=n, session_closed_verified=closed,
             unverified_tail_bytes=len(data)-2*n, rail_samples_recomputed=rails,
             sha256_bin=hashlib.sha256(data).hexdigest(),
             sha256_txt=hashlib.sha256(report_bytes).hexdigest(),
             acquisition_profile='MPU-6500 / 1000 Hz' if fs == 1000 else 'MPU-6050 / 500 Hz (legado)')
    notices.append('Tempo nominal por segmento: não mede jitter, perdas exatas ou frequência calibrada do sensor.')
    return Recording(raw, fs, scale, pd.DataFrame(rows), m, notices)


def read_csv_recording(data, axis=None, unit='g'):
    df = pd.read_csv(io.BytesIO(data), sep=None, engine='python', comment='#')
    df.columns = df.columns.str.strip()
    if 'time_s' not in df: raise ValueError('CSV deve conter time_s em segundos.')
    columns = [c for c in df if c != 'time_s']
    if not columns: raise ValueError('CSV sem coluna de aceleração.')
    axis = axis or ('accel_z_g' if 'accel_z_g' in columns else columns[0])
    if axis not in columns: raise ValueError('Eixo ausente no CSV.')
    def numbers(c): return pd.to_numeric(df[c].astype(str).str.replace(',', '.', regex=False), errors='coerce').to_numpy(float)
    t, x = numbers('time_s'), numbers(axis)
    if len(t) < 16 or not np.isfinite(t).all() or not np.isfinite(x).all(): raise ValueError('CSV contém dados inválidos; nenhuma linha foi removida.')
    dt = np.diff(t)
    if np.any(dt <= 0): raise ValueError('Tempos duplicados ou em ordem inversa; nenhuma linha foi reordenada.')
    med = float(np.median(dt)); fs = 1/med
    boundaries = np.r_[0, np.flatnonzero(dt > 1.5*med)+1, len(t)]
    rows = []
    for ident, (a,b) in enumerate(zip(boundaries[:-1], boundaries[1:]), 1):
        local = np.diff(t[a:b])
        if len(local) and np.max(np.abs(local/med-1)) > .01:
            raise ValueError('CSV irregular dentro de um trecho: não há reamostragem automática.')
        rows.append(dict(segment_id=ident, first_sample=int(a), end_sample_exclusive=int(b),
                         start_arduino_ms=None, stop_arduino_ms=None, reason='CSV',
                         csv_start_s=float(t[a]), csv_end_exclusive_s=float(t[b-1]+med)))
    if unit == 'm/s²': x = x/9.80665
    m = parse_metadata('\n'.join(s for s in data.decode('utf-8-sig').splitlines() if s.strip().startswith('#')))
    if (m.get('status', 'OK') not in ('OK', 'OK_WITH_GAPS') or int(m.get('error_code',0)) or
            int(m.get('fifo_overflows',0)) or m.get('time_basis')=='sample_index_nominal_per_segment'):
        raise ValueError('CSV declara falha/incompletude: utilize o BIN + TXT V2 para conferir os segmentos.')
    m['declared_time_basis']=m.get('time_basis','Não identificada')
    m.update(format='CSV', axis=axis, integrity_verified=False, sha256_input=hashlib.sha256(data).hexdigest(),
             time_basis='CSV informado; sem validação do relógio ou do firmware', columns=columns)
    return Recording(x, fs, 1., pd.DataFrame(rows), m,
                     ['Escala, filtros e origem dos tempos do CSV precisam ser documentados.'])


def synthetic_recording():
    fs = 1000.; t = np.arange(1000000)/fs
    rng = np.random.default_rng(42)
    amplitude = np.where(t >= 900, .35, .045)
    x = 1+amplitude*np.sin(2*np.pi*8*t)+.015*np.sin(2*np.pi*35*t)+rng.normal(0,.012,len(t))
    seg = pd.DataFrame([dict(segment_id=1, first_sample=0, end_sample_exclusive=len(x), reason='sintético')])
    return Recording(x, fs, 1., seg, dict(format='SYNTHETIC', time_basis='sintética',
                     sha256_input=hashlib.sha256(x.tobytes()).hexdigest(), integrity_verified=False), [])
