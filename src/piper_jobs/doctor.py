"""`piper doctor`: check Ollama is reachable, the model is pulled, and it runs on the GPU."""

from __future__ import annotations

from .config import Settings

OK, WARN, FAIL = "[ ok ]", "[warn]", "[FAIL]"


def _same_model(a: str, b: str) -> bool:
    norm = lambda m: m if ":" in m else f"{m}:latest"  # noqa: E731
    return norm(a) == norm(b)


def run_doctor(settings: Settings) -> int:
    import ollama

    print(f"Provider: {settings.llm_provider}   Data dir: {settings.data_dir}")
    if settings.llm_provider != "ollama":
        print(f"{WARN} LLM_PROVIDER is '{settings.llm_provider}', skipping Ollama checks.")
        return 0

    client = ollama.Client(host=settings.ollama_host)
    model = settings.ollama_model

    try:
        listing = client.list()
    except Exception as exc:
        print(f"{FAIL} Ollama is not reachable at {settings.ollama_host} ({exc}).")
        print("       Install it from https://ollama.com/download and make sure it is running.")
        return 1
    print(f"{OK} Ollama reachable at {settings.ollama_host}")

    names = [m.model for m in listing.models]
    if not any(_same_model(n, model) for n in names):
        print(f"{FAIL} Model '{model}' is not pulled. Run:  ollama pull {model}")
        if names:
            print(f"       Pulled models: {', '.join(names)}")
        return 1
    print(f"{OK} Model '{model}' is pulled")

    print("       Loading the model (first load can take a few seconds)...")
    try:
        client.generate(model=model, prompt="Reply with OK.", options={"num_predict": 3}, keep_alive="5m")
    except Exception as exc:
        print(f"{FAIL} Model failed to run: {exc}")
        return 1

    running = [m for m in client.ps().models if _same_model(m.model, model)]
    if not running:
        print(f"{WARN} Model ran but is not listed by `ollama ps`; cannot confirm GPU use.")
        return 0
    m = running[0]
    gb = lambda n: f"{n / 1024**3:.1f} GB"  # noqa: E731
    share = (m.size_vram / m.size) if m.size else 0
    print(f"       ollama ps: {m.model}  size={gb(m.size)}  vram={gb(m.size_vram)}  ({share:.0%} GPU)")
    if share >= 0.99:
        print(f"{OK} Running fully on the GPU")
    elif share > 0:
        print(f"{WARN} Split between GPU and CPU ({share:.0%} GPU). A smaller model or quantization will be faster.")
    else:
        print(f"{WARN} Running on the CPU only. Check your GPU drivers; extraction will be slow.")

    creds = settings.credentials_path
    gmail = "connected" if settings.token_path.is_file() else (
        "credentials.json found, not authorized yet" if creds.is_file() else f"no credentials.json at {creds}")
    print(f"       Gmail: {gmail}")
    return 0
