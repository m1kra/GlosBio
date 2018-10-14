from pydub import AudioSegment


def convert_webm_to_format(source_path: str, destination_path: str,
                           format : str = "wav"):
    """ Helper function converting webm to wav so it can be handled
   by mainstream libraries

   :param source_path: str path to source
   :param destination_path: str path to save to without format
   :param format: intended format without ., e.g. wav
   """

    sound = AudioSegment.from_file(
        source_path,
        codec="opus"
    ).export(destination_path+"."+format, format=format)
