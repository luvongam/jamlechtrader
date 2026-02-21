# Dockerfile.windows
# Windows Server Core with MT5 support

FROM mcr.microsoft.com/windows/servercore:ltsc2022

# Install Python
RUN powershell -Command \
    Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe -OutFile python-installer.exe; \
    Start-Process python-installer.exe -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -Wait; \
    Remove-Item python-installer.exe

# Install MetaTrader 5
RUN powershell -Command \
    Invoke-WebRequest -Uri https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe -OutFile mt5setup.exe; \
    Start-Process mt5setup.exe -ArgumentList '/auto' -Wait; \
    Remove-Item mt5setup.exe

# Set working directory
WORKDIR C:\\app

# Copy application
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[mt5,reports,dev]"

# Expose ports for API access
EXPOSE 8000

# Run the bot
CMD ["python", "main.py", "live", "-s", "advanced_smc"]
