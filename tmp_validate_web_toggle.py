import json
import uuid
import urllib.request

base = "http://localhost:8000/api/v1/workspace"
client_id = str(uuid.uuid4())


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode())


conv = post_json(
    f"{base}/conversations",
    {"client_id": client_id, "mode": "general", "title": "Nova conversa"},
)
conv_id = conv["id"]

ans1 = post_json(
    f"{base}/conversations/{conv_id}/messages",
    {
        "client_id": client_id,
        "content": "Quais as cores do arco-íris?",
        "web_search_enabled": False,
    },
)["answer"]

ans2 = post_json(
    f"{base}/conversations/{conv_id}/messages",
    {
        "client_id": client_id,
        "content": "Sim, procure",
        "web_search_enabled": False,
    },
)["answer"]

ans3 = post_json(
    f"{base}/conversations/{conv_id}/messages",
    {
        "client_id": client_id,
        "content": "Qual foi o PIB do Brasil em 2025?",
        "web_search_enabled": True,
    },
)["answer"]

print("CONVERSA:", conv_id)
print("\n[1] Sem busca web:\n", ans1[:450])
print("\n[2] Confirmação -> busca externa:\n", ans2[:550])
print("\n[3] Busca web ativada:\n", ans3[:550])
