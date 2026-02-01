# QuantSight Cloud - Firebase Studio Environment Configuration
# To learn more: https://developers.google.com/idx/guides/customize-idx-env
{ pkgs, ... }: {
  # Firebase Studio channel (Nix packages version)
  channel = "stable-24.05";
  
  # Packages available in the development environment
  packages = [
    # Python ecosystem
    pkgs.python312
    pkgs.python312Packages.pip
    pkgs.python312Packages.virtualenv
    
    # Node.js for frontend
    pkgs.nodejs_20
    
    # PostgreSQL client (for Cloud SQL connections)
    pkgs.postgresql
    
    # Build tools
    pkgs.gcc
    pkgs.gnumake
    
    # Cloud tools
    pkgs.google-cloud-sdk
  ];
  
  # Environment variables
  env = {
    PYTHON_VERSION = "3.12";
  };
  
  # IDE configuration
  idx = {
    # Workspace lifecycle hooks
    onStart = {
      # Install Python dependencies
      install-python-deps = "cd backend && pip install -r requirements.txt";
    };
    
    # Preview configuration for Cloud Run
    previews = {
      enable = true;
      previews = {
        web = {
          command = ["uvicorn" "backend.server:app" "--host" "0.0.0.0" "--port" "$PORT"];
          manager = "web";
        };
      };
    };
  };
}
