import kagglehub

# Download latest version
path = kagglehub.dataset_download("marcodena/mobile-phone-activity")

print("Path to dataset files:", path)