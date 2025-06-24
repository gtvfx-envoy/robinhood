def load_json_file(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

def save_json_file(filepath, data):
    with open(filepath, "w") as file:
        json.dump(data, file, indent=2)

def load_csv_file(filepath):
    if not os.path.exists(filepath):
        return None
    return pd.read_csv(filepath)

def save_csv_file(filepath, data):
    data.to_csv(filepath, index=False)

def log_message(message, log_file):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(log_file, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry + "\n")