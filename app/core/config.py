import os
from google.cloud import secretmanager

class AppConfig:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID", "quantsight-prod")
        self.environment = os.getenv("APP_ENV", "development")
        self.client = secretmanager.SecretManagerServiceClient() if self.environment != "development" else None

    def get_secret(self, secret_id: str) -> str:
        if self.environment == "development":
            return os.getenv(secret_id, "dev_mock_secret")
            
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
        try:
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"Failed to fetch secret {secret_id}: {e}")
            return ""

config = AppConfig()
