import psutil

app_list = {"Google Chrome"}

found = False

print("Scanning running processes...")
for proc in psutil.process_iter(attrs=['pid', 'name']):
    try:
        name = proc.info['name']
        if name in app_list:
            print(f"Found BCI2000 process: {name} (PID: {proc.info['pid']})")
            found = True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue

if not found:
    print("No BCI2000 processes found.")