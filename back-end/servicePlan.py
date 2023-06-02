class servicePlan:
    def __init__(self, max_download_speed, max_upload_speed, isp_name, technology_type):
        self._max_download_speed = max_download_speed
        self._max_upload_speed = max_upload_speed
        self._isp_name = isp_name
        self._technology_type = technology_type

    @property
    def max_download_speed(self):
        return self._max_download_speed

    @max_download_speed.setter
    def max_download_speed(self, value):
        self._max_download_speed = value

    @property
    def max_upload_speed(self):
        return self._max_upload_speed

    @max_upload_speed.setter
    def max_upload_speed(self, value):
        self._max_upload_speed = value

    @property
    def isp_name(self):
        return self._isp_name

    @isp_name.setter
    def isp_name(self, value):
        self._isp_name = value

    @property
    def technology_type(self):
        return self._technology_type

    @technology_type.setter
    def technology_type(self, value):
        self._technology_type = value

    def lookup_tech_code(self, number):
        def lookup_dropdown_value(value):
            options = {
                "10": "Copper Wire",
                "40": "Coaxial Cable / HFC",
                "50": "Optical Carrier / Fiber to the Premises",
                "60": "Geostationary Satellite",
                "61": "Non-geostationary Satellite",
                "70": "Unlicensed Terrestrial Fixed Wireless",
                "71": "Licensed Terrestrial Fixed Wireless",
                "72": "Licensed-by-Rule Terrestrial Fixed Wireless",
                "0": "Other"
            }
            return options.get(value, "Invalid value")

