FROM nodered/node-red:latest

# Install palette packages
RUN npm install --unsafe-perm --no-update-notifier \
    node-red-dashboard \
    node-red-contrib-modbus \
    node-red-contrib-ui-led

# Copy default flows
COPY flows.json /data/flows.json
COPY settings.js /data/settings.js
