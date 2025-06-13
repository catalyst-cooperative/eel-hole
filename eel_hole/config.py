import os


class BaseConfig:
    SECRET_KEY = os.getenv("PUDL_VIEWER_SECRET_KEY")
    TEMPLATES_AUTO_RELOAD = True
    LOGIN_DISABLED = os.getenv("PUDL_VIEWER_LOGIN_DISABLED", "false").lower() == "true"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FEATURE_FLAGS = {
        "ferc_enabled": os.getenv("FEATURE_FERC_ENABLED", "false").lower() == "true"
    }

    # Set this only if running in Cloud Run
    if os.getenv("IS_CLOUD_RUN"):
        PREFERRED_URL_SCHEME = "https"


class DevConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProdConfig(BaseConfig):
    DEBUG = False
