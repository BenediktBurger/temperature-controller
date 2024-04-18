"""
A file for defining information about the connections, including passwords.
This file should not be published via git. Protect it as necessary.

Created on Mon Jun 14 11:27:35 2021 by Benedikt Burger
"""

# Change the data in order to fit the database. Rename this file to "connectionData.py".
database = {'host': "HOST-NAME",  # Host name of the server.
            'port': 5432,
            'database': "DATABASE-NAME",  # Database on that server.
            'user': "USER-NAME",
            'password': "USER-PASSWORD"
            }

# LECO coordinator address
# use ":" for a port, for example "example.server:12345"
leco_coordinator_host_address = "localhost"
