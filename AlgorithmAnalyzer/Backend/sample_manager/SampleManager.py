import io
import os
import re
import unicodedata
import json
from io import BytesIO
from typing import *


from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from scipy.io import wavfile
from pathlib import Path

from utils import convert_webm
from utils.speech_recognition_wrapper import speech_to_text_wrapper
from plots import mfcc_plot
from config import ALLOWED_PLOT_TYPES_FROM_SAMPLES

''''''''''''''''
example of directory structure

data/    <---- root directory
├── hugo_kolataj
│   ├── 1.json
│   ├── 1.wav   <----- sample from 'train' set
│   └── test
│       ├── 1.json
│       ├── 1.wav
│       ├── 2.json
│       ├── 2.wav    <----- sample from 'test' set
│       ├── 3.json
│       └── 3.wav
└── stanislaw_golebiewski  <---- username / user directory
    ├── 1.json
    ├── 1.wav
    ├── 2.json
    ├── 2.wav
    ├── 3.json
    ├── 3.wav
    └── test   <---- test set directory
        ├── 1.json
        ├── 1.wav
        ├── 2.json    <---- json file associated with sample '2.wav'
        └── 2.wav

'''''''''''''''


class UsernameException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)


class SampleManager:
    # TODO: this class handles way too many things
    #  Needs to follow underscore (_get..) convention to denote private methods
    #  Some methods not used at all
    #  Rewrite to use DB?

    def __init__(self, path):
        """path:  string or path; path to root directory"""

        self.path = os.path.normpath(path)

    def _mkdir(self, name):
        if self._user_directory_exists(name):
            return
        os.makedirs(os.path.join(self.path, name))

    def get_all_usernames(self):
        d = []
        for (dirpath, dirnames, filenames) in os.walk(self.path):
            d.extend(dirnames)
            break
        return d

    def _user_directory_exists(self, dirname):
        return os.path.isdir(os.path.join(self.path, dirname))

    def user_exists(self, username):
        user = self.username_to_dirname(username)
        return self._user_directory_exists(user)

    def file_exists(self, username, type, sample):
        dir = self.get_user_dirpath(username)
        if type == 'test':
            dir = os.path.join(dir, type)
        return Path(os.path.join(dir, sample)).exists()

    def create_user(self, username):
        user = self.username_to_dirname(username)
        self._mkdir(user)
        self._mkdir(os.path.join(user, 'test'))

    def get_samples(self, username, set_type='train'):
        user = self.username_to_dirname(username)
        samples = []
        if set_type == 'train':
            samples = list(os.listdir(os.path.join(self.path, user)))
            samples.remove('test')
        else:
            samples = list(os.listdir(os.path.join(self.path, user, 'test')))
        rgx = re.compile('.+\.wav$')
        return list(filter(rgx.match, samples))

    def get_new_sample_path(self, username, set_type="train", filetype="wav", no_file_type=False):
        samples = self.get_samples(username, set_type)
        username = self.username_to_dirname(username)

        if samples:
            last_sample = max(
                int(name.split('.')[0]) for name in samples
            )
        else:
            last_sample = 0
        out_path = os.path.join(self.path, username)
        if set_type == 'test':
            out_path = os.path.join(out_path, set_type)

        if not no_file_type:
            return os.path.join(out_path, str(last_sample + 1) + '.' + filetype)
        else:
            return os.path.join(out_path, str(last_sample + 1))

    def get_user_dirpath(self, username, set_type = None):
        if set_type == "test":
            return os.path.join(self.path, self.username_to_dirname(username), set_type)
        return os.path.join(self.path, self.username_to_dirname(username))


    def _get_new_extension_path(self, audio_path: str, format: str) -> str:
        """ this gets path for the audio's accompanying file
        of the format extension based on str audio_path

         :param format: desired format without '.', e.g. 'pdf', 'json'
         e.g C:/aasda/a.wav -> C:/aasda/a_type.format"""
        return audio_path.rsplit('.', 1)[0]+f".{format}"

    def add_sample(self, username, sample):
        '''
            this method serves to save samples
            for now it's not used
        '''
        # TODO Not used anywhere..
        new_path = self.get_new_sample_path(username)
        with open(new_path, 'wb') as new:
            new.write(sample)

    def get_sample(self, username, sample_number):
        # TODO: doesn't get samples for test/train...?
        username = self.username_to_dirname(username)
        sample_path = os.path.join(
            self.path, username,
            '{}.wav'.format(sample_number)
        )
        return wavfile.read(sample_path)

    def _get_wav_sample_expected_file_path(self, username, sample_name: str, sample_type: str) -> str:
        #TODO: Not unit tested!
        """
        Returns the sample's filepath

        :param username: normalized or raw user's name
        :param sample_name: sample's name without extension, e.g. '1'
        :param sample_type: 'train' or 'test
        :return: str with the expected sample path
        """
        # normalize username
        username = self.username_to_dirname(username)

        # drop file extension if it was passed alongside
        sample_name = sample_name.rsplit(".")[0]

        # handle sample_type path change
        if sample_type == "train":
            sample_path = os.path.join(
                self.path, username,
                '{}.wav'.format(sample_name)
            )
        else:
            sample_path = os.path.join(
                self.path, username, sample_type,
                '{}.wav'.format(sample_name)
            )

        return sample_path


    def _invalid_username(self, username):
        return not re.match('^\w+$', username)

    # TODO: ???? commented out
    # def save_new_sample(self, username: str, file: FileStorage, type: str) -> str:
    #     if not self.user_exists(username):
    #         self.create_user(username)
    #     path = self.get_new_sample_path(username, set_type=type, filetype="webm")
    #     file.save(path)
    #     return path

    @staticmethod
    def is_allowed_file_extension(file: FileStorage) -> bool:
        """
        checks whether mimetype of the file is allowed
        :param file: FileStorage
        :return: True/False
        """
        return True if file.mimetype == "audio/wav" else False

    def save_new_sample(self, username: str, file: FileStorage, set_type: str) -> Tuple[str, str]:
        """
        saves new sample as both .webm and wav with a JSON file
        :param username: str
        :param file: FileStorage
        :return: str wav_path, str recognized_speech
        """
        # TODO: FileStorage is hard to mock in tests
        #  Perhaps could handle both standard and FileStorage files
        if not self.user_exists(username):
            self.create_user(username)

        if self.is_allowed_file_extension(file):
            wav_path = self.get_new_sample_path(username, set_type=set_type, filetype="wav")
            file.save(wav_path)
            print(f"#LOG {self.__class__.__name__}: .wav file saved to: " + wav_path)
        else:
            # not-wav file is temporarily saved
            temp_path = self.get_new_sample_path(username, set_type=set_type, no_file_type=True)
            print()
            file.save(temp_path)

            # convert to webm

            # get a BytesIO object
            with open(temp_path, 'rb') as webm_input_file_handle:
                webm_input_bytesIO = BytesIO(webm_input_file_handle.read())

            # convert in memory webm to wav
            wav_output_bytesIO = convert_webm.convert_webm_to_format(
                webm_input_bytesIO,  "wav")

            # get a new wav path
            wav_path = os.path.splitext(temp_path)[0]+'.wav'
            # save the newly converted file to wav_path
            with open(wav_path, 'wb') as new_wav_file:
                new_wav_file.write(wav_output_bytesIO.getvalue())

            print("#LOG {self.__class__.__name__}: .wav file converted and saved to: " + wav_path)

            # delete temp file
            os.remove(temp_path)

        # recognize speech
        recognized_speech = speech_to_text_wrapper.recognize_speech_from_path(wav_path)
        print(f"#LOG {self.__class__.__name__}: Recognized words: {recognized_speech}")

        # save the new sample json
        json_path = self.create_new_sample_properties_json(username, audio_path=wav_path,
                                                           data={"recognized_speech": recognized_speech})
        print(f"#LOG {self.__class__.__name__}: Created a JSON file: {json_path}")


        return wav_path, recognized_speech

    def create_new_sample_properties_json(self, username, data: Dict[str, str], audio_path: str) -> str:
        """
        this creates a json file for the newest sample for the username given
        e.g: 5.json
        takes data to be saved in the form of dict[string, string]
        audio_path is a path to the audio file to be accompanied by json file
        :param username: str
        :param data: typing.Dict[str, str]
        :param audio_path: str path to audio
        :return: str path to json
        """
        json_path = self._get_new_extension_path(audio_path, 'json')
        with open(json_path, 'w', encoding='utf8') as json_file:
            recording_properties = {"name": username, **data}
            string_json = str(json.dumps(recording_properties, ensure_ascii=False).encode('utf8'), encoding='utf8')
            json_file.writelines(string_json)
        return json_path

    def create_plot_for_sample(self, plot_type: str, set_type: str,
                               username: str, sample_name: str,
                               file_extension: str = "png", **parameters) -> Tuple[str, bytes]:
        """
        Master method that creates a plot of given plot_type (e.g. "mfcc")
        for a given set_type (train, test), username and specific sample
        file_extension can be specified (png or pdf)

        :param plot_type: str type of plot, e.g. "mfcc"
        :param set_type: set of users' sample, test or train
        :param username: str normalized username of the user
        :param sample_name: str name of the sample, e.g. "1.wav"
        :param file_extension: pdf or png file extension of the plot file
        :param parameters: extra plot type specific parameters, pass as keyworded
        e.g. alfa=10, beta=20
        :return file_path, file_io: str file_path to the saved file,
        BytesIO containing the requested plot
        """
        wav_path = self._get_wav_sample_expected_file_path(username, sample_type=set_type,
                                                           sample_name=sample_name)
        directory_path = self.get_user_dirpath(username, set_type=set_type)

        # see if a plot already exists
        # if it does, send it instead of remaking it
        try:
            file_path, file_bytes = self._get_plot_for_sample_file(wav_path, plot_type, file_extension)
        except FileNotFoundError:
            # the plot does not exists, gonna make it!
            if plot_type == "mfcc":
                file_path, file_bytes = self._create_plot_mfcc_for_sample(audio_path=wav_path,
                                                  directory_path=directory_path,
                                                  file_extension=file_extension)
            else:
                raise ValueError("plot_type should be of type str, of value one of "
                                 f"{ALLOWED_PLOT_TYPES_FROM_SAMPLES}")

            return file_path, file_bytes

    def _create_plot_mfcc_for_sample(self, audio_path: str, directory_path: str,
                                     file_extension: str = "png") -> Tuple[str, bytes]:
        """
        This creates a MFCC plot file of file_extension file (pdf or png)
        for the audio_path file given.
        The plot is saved in the user+type dirpath.

        :param audio_path: str full path to the sample file
        :param directory_path: str full path to the sample's directory,
        e.g username/ or username/set_type
        :param file_extension: pdf or png file extension of the plot mfcc file
        :return file_path, file_io: str file_path to the saved file,
        BytesIO containing the requested plot
        """
        # TODO: Not unit tested!
        file_name = f"{self._get_sample_file_name_from_path(audio_path)}_mfcc"
        file_path, file_io = mfcc_plot.plot_save_mfcc_color_boxes(audio_path, directory_path,
                                                         file_name, file_extension)

        print(f"#LOG {self.__class__.__name__}: mfcc plot file saved to: " + file_path)
        return file_path, file_io.getvalue()


    def _get_plot_for_sample_file(self, audio_path: str, plot_type: str,
                                  file_extension: str = "png") -> Tuple[str, bytes]:
        """
        This helper gets str plot's path and plot's content as BytesIO
        based on str audio_path of the
        with a file_extension given (or None for png)
        already exists

        :param audio_path: str full path to the sample file
        :param plot_type: str type of plot, e.g. "mfcc"
        :param file_extension: pdf or png file extension of the plot mfcc file
        :raises FileNotFoundError:
        :return: str path to the plot, and BytesIO plot's contents
        """
        # TODO: This will have to be remade once a new SampleManager rolls out
        # TODO: NOT UNIT TESTED AWAITING FOR CHANGE
        expected_plot_path =  f"{self._get_sample_file_name_from_path(audio_path)}_{plot_type.lower()}.{file_extension.lower()}"
        with open(expected_plot_path, mode='rb') as plot_file:
            return expected_plot_path, io.BytesIO(plot_file.read()).getvalue()


    def _get_sample_file_name_from_path(self, file_path: str) -> str:
        """
        Gets the number of the sample provided its file
        e.g: "c:/app/2.wav -> 2"

        :param file_path: str path to the file
        :return: str file name without its extension
        """
        path = Path(file_path)
        return path.stem

    def is_wav_file(self, samplename):
        return re.match('.+\.wav$', samplename)

    def username_to_dirname(self, username: str):
        '''
        Convert username, which could include spaces,
        big letters and diacritical marks, to valid directory name
        '''

        temp = username.lower()
        d = {
            "ą": "a",
            "ć": "c",
            "ę": "e",
            "ł": "l",
            "ó": "o",
            "ś": "s",
            "ź": "z",
            "ż": "z"
        }
        for diac, normal in d.items():
            temp = temp.replace(diac, normal)
        temp = temp.replace(" ", "_")
        temp = unicodedata.normalize('NFKD', temp).encode('ascii', 'ignore').decode('ascii')
        if self._invalid_username(temp):
            raise UsernameException(
                'Incorrect username "{}" !'.format(temp)
            )
        return secure_filename(temp)

    def file_has_proper_extension(self, filename: str, allowed_extensions: list) -> Tuple[bool, str]:
        """
        it takes 'filename' and decide if it has extension which can be found
        in 'allowed_extensions'
      
        important: extensions in 'allowed_extensions' should not start with dot, eg:
           good: ['webm', 'cat', 'wav']
           bad:  ['.webm', '.cat', '.wav']
        """
        # regular expression for files with extensions (file).(extension)
        regex = re.match('(.+)\.(.+$)', filename)
        if not regex:
            return False, ""
        else:
            file_extension = regex.group(2)
            if file_extension not in allowed_extensions:
                return False, file_extension
            else:
                return True, file_extension
