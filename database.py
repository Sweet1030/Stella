import json

def save_data(data, filename="data.json"):
    """데이터를 JSON 파일로 저장"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_data(filename="data.json"):
    """JSON 파일에서 데이터 불러오기"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}