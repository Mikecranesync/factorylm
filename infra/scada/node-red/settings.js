module.exports = {
    flowFile: "flows.json",
    uiPort: process.env.PORT || 1880,
    uiHost: "0.0.0.0",
    httpAdminRoot: "/",
    httpNodeRoot: "/",
    ui: { path: "ui" },
    functionGlobalContext: {
        PLC_API_URL: process.env.PLC_API_URL || "http://localhost:8001",
        DIAGNOSIS_URL: process.env.DIAGNOSIS_URL || "http://localhost:8200",
        MODBUS_HOST: process.env.MODBUS_HOST || "localhost",
        MODBUS_PORT: parseInt(process.env.MODBUS_PORT || "502"),
        WEBCAM_URL: process.env.WEBCAM_URL || "http://100.72.2.99:8081/stream"
    },
    logging: {
        console: { level: "info", metrics: false, audit: false }
    }
};
