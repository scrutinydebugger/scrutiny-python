class InvalidRequestException(Exception):
    def __init__(self, req, *args, **kwargs):
        self.request = req
        super().__init__(*args, **kwargs)


class InvalidResponseException(Exception):
    def __init__(self, response, *args, **kwargs):
        self.response = response
        super().__init__(*args, **kwargs)