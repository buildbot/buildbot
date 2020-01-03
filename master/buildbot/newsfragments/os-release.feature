bb:cfg:`workers` will now attempt to read ``/etc/os-release`` and stores them into worker info as ``os_<field>`` items.
Add new interpolation ``worker`` that can be used for accessing worker info items.
