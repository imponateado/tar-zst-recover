import subprocess
import sys
import os

FILE = "homebkp.tar.zst"
CHUNK = 1024 * 1024  # 1MB por vez

SIGS = {
    b"ustar":           "tar",
    b"\x28\xb5\x2f\xfd": "zstd",
    b"\x1f\x8b":         "gzip",
}


def find_signatures(filepath):
    found = {sig: [] for sig in SIGS}
    size = os.path.getsize(filepath)
    with open(filepath, "rb") as f:
        pos = 0
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            for sig in SIGS:
                idx = 0
                while True:
                    i = chunk.find(sig, idx)
                    if i == -1:
                        break
                    found[sig].append(pos + i)
                    idx = i + 1
            pos += len(chunk)
            print(f"\r  Escaneando... {pos / size * 100:.1f}%", end="", flush=True)
    print()
    return found


def is_success(out):
    return any(c in out for c in ["drwx", "-rw-", "lrwx", "drwxr", "./", "2024-", "2025-", "2026-"])


def try_tar(offset, label):
    print(f"\n[{label}] tar raw a partir de offset {offset}...")
    result = subprocess.run(
        f"dd if={FILE} bs=4M skip={offset} iflag=skip_bytes 2>/dev/null | tar -tvif - 2>&1 | head -20",
        shell=True, capture_output=True, text=True
    )
    out = result.stdout + result.stderr
    if is_success(out):
        print(f"  ✓ SUCESSO! Arquivos encontrados:")
        print(out[:800])
        return True
    print(f"  ✗ {out[:120].strip()}")
    return False


def try_zstd_tar(offset, label):
    print(f"\n[{label}] zstd+tar a partir de offset {offset}...")
    result = subprocess.run(
        f"dd if={FILE} bs=4M skip={offset} iflag=skip_bytes 2>/dev/null | zstd -d --no-check 2>/dev/null | tar -tvif - 2>&1 | head -20",
        shell=True, capture_output=True, text=True
    )
    out = result.stdout + result.stderr
    if is_success(out):
        print(f"  ✓ SUCESSO!")
        print(out[:800])
        return True
    print(f"  ✗ {out[:120].strip()}")
    return False


def find_next_ustar(from_offset):
    """Encontra o próximo 'ustar' a partir de from_offset, lendo em chunks."""
    sig = b"ustar"
    file_size = os.path.getsize(FILE)
    with open(FILE, "rb") as f:
        f.seek(from_offset)
        pos = from_offset
        while pos < file_size:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            idx = chunk.find(sig)
            if idx != -1:
                return pos + idx
            pos += len(chunk)
    return None


def try_extract(offset, outdir):
    """Extrai em loop, pulando blocos corrompidos e continuando do próximo ustar."""
    os.makedirs(outdir, exist_ok=True)
    logfile = os.path.join(outdir, "extract.log")
    print(f"\nExtraindo para {outdir}...")
    print(f"Log em {logfile}")

    current_offset = offset
    total_extracted = 0
    file_size = os.path.getsize(FILE)

    with open(logfile, "w") as log:
        while current_offset < file_size:
            print(f"\n  → Offset {current_offset} ({current_offset / file_size * 100:.1f}%)...")
            result = subprocess.run(
                f"dd if={FILE} bs=4M skip={current_offset} iflag=skip_bytes 2>/dev/null"
                f" | tar -xvif - --ignore-failed-read -C {outdir} 2>&1",
                shell=True, capture_output=True, text=True
            )
            out = result.stdout + result.stderr
            log.write(out)
            log.flush()

            extracted = [l for l in out.splitlines() if l.startswith("home/") or l.startswith("./")]
            total_extracted += len(extracted)
            if extracted:
                print(f"  ✓ {len(extracted)} arquivos extraídos")
                for line in extracted[:5]:
                    print(f"    {line}")
                if len(extracted) > 5:
                    print(f"    ... e mais {len(extracted) - 5}")

            next_ustar = find_next_ustar(current_offset + 512 * 1024)
            if next_ustar is None or next_ustar <= current_offset:
                print("\n  Sem mais blocos ustar. Extração concluída.")
                break
            current_offset = next_ustar - 265

    print(f"\n★ Total extraído: {total_extracted} arquivos → {outdir}")
    print(f"  Log completo: {logfile}")


def main():
    if not os.path.exists(FILE):
        print(f"Arquivo não encontrado: {FILE}")
        print("Rode o script na mesma pasta do arquivo.")
        sys.exit(1)

    print(f"Escaneando {FILE} ({os.path.getsize(FILE) / 1e9:.1f} GB)...")
    found = find_signatures(FILE)

    print("\n=== Assinaturas encontradas ===")
    for sig, positions in found.items():
        name = SIGS[sig]
        print(f"  {name}: {len(positions)} ocorrências → primeiros offsets: {positions[:5]}")

    good_offset = None

    # Tenta tar raw a partir de cada ustar encontrado
    ustar_positions = found[b"ustar"]
    for ustar_pos in ustar_positions[:10]:
        for delta in [257, 265, 0, 512, 256, 128, 384, 64, 32, 16, 8]:
            offset = max(0, ustar_pos - delta)
            if try_tar(offset, f"ustar@{ustar_pos} delta={delta}"):
                good_offset = offset
                break
        if good_offset is not None:
            break

    # Tenta zstd+tar a partir de cada magic zstd encontrado
    if good_offset is None:
        for zstd_pos in found[b"\x28\xb5\x2f\xfd"][:5]:
            if try_zstd_tar(zstd_pos, f"zstd@{zstd_pos}"):
                good_offset = zstd_pos
                break

    if good_offset is None:
        print("\n✗ Nenhuma combinação funcionou automaticamente.")
        print("\nOffsets ustar para inspeção manual:")
        for p in ustar_positions[:10]:
            print(f"  decimal={p}  hex=0x{p:08x}")
        sys.exit(1)

    print(f"\n★ OFFSET CORRETO ENCONTRADO: {good_offset}")
    answer = input("Deseja extrair os arquivos agora? [s/N] ").strip().lower()
    if answer == "s":
        try_extract(good_offset, os.path.expanduser("~/recovered"))


if __name__ == "__main__":
    main()
