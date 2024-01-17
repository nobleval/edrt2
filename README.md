To download the global configuration file from a Ecodevices RT2 and to modify hourly, daily or current index and price values in case of wrong registered data for example.
The new configuration file can be uploaded to the device to come back to a satisfying situation.

Limitations
- Only tested with a 3.00.04 software and firmware version.
- The upload feature is present but has not been tested. The manual upload with the provided web interface is recommended.

Notes
- The time gap between the download and the upload must be as short as possible in order to loose the less consomption counting as possible. It is recommended to download a first time, to code the modifications in the script, to check the new file obtained, to download a second time and to make immediately effective the modifications in the file just before uploading it.
- The operation should be avoided just before a plain hour (at the time when hourly values are registered in the history) and when the current consomption of one or more counters is high (because current values will be replaced by the ones located in the file).
- The X-THL values are not impacted (registered values in the device are kept). The X-THL values are not part of the global configuration file.
