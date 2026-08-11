# Exam Centre Network Refresh

The offline/LAN Exam Centre now detects the server laptop's current LAN IPv4 address whenever the page loads.

It also:
- rechecks the LAN address every 15 seconds while the Exam Centre page is open;
- provides a **Refresh Network** button for an immediate manual check;
- updates the Student URL, displayed LAN IP, Open Login Page link, and QR code together when the address changes;
- sends the network-info response with no-cache headers.

Online mode continues to use the fixed hosted domain and does not show the LAN refresh button.
