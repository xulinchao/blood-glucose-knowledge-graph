"""Helper script: append new topics to discovered-topics.json safely."""
import json, sys

TOPICS_PATH = r"I:\Project\血糖知识图谱\data\discovered-topics.json"

def load():
    with open(TOPICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    with open(TOPICS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def max_id(data):
    ids = []
    for t in data["topics"]:
        try:
            n = int(t["id"].split("-")[1])
            ids.append(n)
        except (ValueError, KeyError, IndexError):
            pass
    return max(ids) if ids else 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    data = load()
    if cmd == "info":
        mid = max_id(data)
        print(json.dumps({
            "total": len(data["topics"]),
            "max_id": f"disc-{mid:03d}",
            "updated": data.get("updated", "")
        }, ensure_ascii=False, indent=2))
    elif cmd == "append":
        import sys
        source_path = sys.argv[2]
        with open(source_path, "r", encoding="utf-8") as f:
            new_topics = json.load(f)
        mid = max_id(data)
        for i, t in enumerate(new_topics):
            mid += 1
            t["id"] = f"disc-{mid:03d}"
            t.setdefault("status", "discovered")
            t.setdefault("script_status", "pending")
            t.setdefault("publish_status", "pending")
            t.setdefault("discovered_date", "2026-11-10")
            data["topics"].append(t)
        data["updated"] = "2026-11-10"
        save(data)
        print(f"Appended {len(new_topics)} topics. New max_id: disc-{mid:03d}")
