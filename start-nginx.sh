#!/usr/bin/expect -f

# Read the passphrase from a file
set timeout -1
set passphrase [read [open "/ssl/passphrase_file" r]]

# Start Nginx and provide the passphrase when prompted
spawn nginx

expect {
    "Enter PEM pass phrase:" {
        send "$passphrase\r"
        exp_continue
    }
}

# Keep the script running to not exit the container
interact
