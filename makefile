.PHONY: install-deps install-app install-service uninstall reinstall update-deps

# Check for root permission
ifneq ($(shell id -u), 0)
$(error "Must be run with sudo")
endif

# Variables
INSTALL_DIR=/opt/natalie-assistant
SERVICE_NAME=natalie
# Hash of requirements file for checking changes
REQUIREMENTS_HASH=.requirements_hash

all: install

# Install Python dependencies
install-dependencies:
	@echo "Installing system dependencies..."
	@sudo apt-get update
	@sudo apt-get install -y python3-pyaudio
	@echo "Installing Python dependencies..."
	@sudo pip install -r requirements.txt
	@sha256sum requirements.txt | awk '{print $$1}' > $(REQUIREMENTS_HASH)

# Install the application
install-app:
	@echo "Installing application to $(INSTALL_DIR)..."
	@sudo mkdir -p $(INSTALL_DIR)
	@sudo rsync -av --exclude '.git/' --exclude '.gitignore' --delete ./ $(INSTALL_DIR)/
	@sudo dos2unix $(INSTALL_DIR)/natalie.py
	@sudo chmod +x $(INSTALL_DIR)/natalie.py

# Create and enable systemd service
install-service:
	@echo "Creating systemd service..."
	@echo "[Unit]" > natalie.service
	@echo "Description=$(SERVICE_NAME)" >> natalie.service
	@echo "After=network.target" >> natalie.service
	@echo "" >> natalie.service
	@echo "[Service]" >> natalie.service
	@echo "ExecStart=$(INSTALL_DIR)/natalie.py" >> natalie.service
# 	@echo "StandardOutput=file:/var/log/$(SERVICE_NAME).out" >> natalie.service
	@echo "StandardError=file:/var/log/$(SERVICE_NAME).err" >> natalie.service
	@echo "User=root" >> natalie.service
	@echo "Restart=always" >> natalie.service
	@echo "RestartSec=5" >> natalie.service
	@echo "" >> natalie.service
	@echo "[Install]" >> natalie.service
	@echo "WantedBy=multi-user.target" >> natalie.service
	@sudo mv natalie.service /etc/systemd/system/$(SERVICE_NAME).service
	@sudo systemctl daemon-reload
	@sudo systemctl enable $(SERVICE_NAME).service


# Master install rule
install: install-dependencies install-app install-service
	@echo "Installation complete. DO NOT FORGET to update $(INSTALL_DIR)/.env before starting the service with systemctl."

# Update Python dependencies
update-deps:
	@echo "Updating Python dependencies..."
	@sudo pip install --upgrade -r requirements.txt
	@sha256sum requirements.txt | awk '{print $$1}' > $(REQUIREMENTS_HASH)

# Update the application from the Git repository
update-app:
	@echo "Fetching latest code from Git repository..."
	@git pull origin master
	@echo "Checking if requirements.txt has changed..."
	@NEW_HASH=$$(sha256sum requirements.txt | awk '{print $$1}'); \
	OLD_HASH=$$(cat $(REQUIREMENTS_HASH) 2>/dev/null); \
	if [ "$$NEW_HASH" != "$$OLD_HASH" ]; then \
		echo "Updating Python dependencies..."; \
		sudo pip install -r requirements.txt; \
		echo $$NEW_HASH > $(REQUIREMENTS_HASH); \
	fi
	@echo "Updating code in $(INSTALL_DIR)..."
	@sudo rsync -av --exclude '.git/' --exclude '.gitignore' ./ $(INSTALL_DIR)/
	@sudo dos2unix $(INSTALL_DIR)/natalie.py
	@sudo systemctl restart $(SERVICE_NAME).service
	@echo "Code and service updated."

# Uninstall the application and service
uninstall:
	@sudo systemctl stop $(SERVICE_NAME).service
	@sudo systemctl disable $(SERVICE_NAME).service
	@sudo rm /etc/systemd/system/$(SERVICE_NAME).service
	@sudo rm -rf $(INSTALL_DIR)
	@sudo systemctl daemon-reload
	@echo "Service $(SERVICE_NAME) and application uninstalled."

# Reinstall the service and application
reinstall: uninstall all install-service
	@echo "Application and service reinstalled."