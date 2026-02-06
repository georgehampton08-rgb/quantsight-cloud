# QuantSight Cloud - Firebase Studio Environment
# To learn more: https://developers.google.com/idx/guides/customize-idx-env
{
  # Nix packages channel
  channel = "stable-24.05";
  
  # Development packages
  packages = [
    "python312"
    "python312Packages.pip"
    "nodejs_20"
    "postgresql"
  ];
  
  # IDE extensions
  idx.extensions = [
    "ms-python.python"
  ];
  
  # Preview configuration
  idx.previews = {
    enable = true;
    previews = {
      web = {
        command = ["python" "backend/server.py"];
        manager = "web";
        env = {
          PORT = "$PORT";
        };
      };
    };
  };
}
