import random

from algorithms.base_algorithm import Algorithm


class EasyExample(Algorithm):
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def get_parameters(cls):
        return {}

    def train(self, *args, **kwargs):
        pass

    def save(self, *args, **kwargs):
        pass

    def load(self, *args, **kwargs):
        pass

    def predict(self, data):
        return bool(random.randint(0, 1)), {}