import sys
import os
import json
import shutil
import tempfile
import ctypes
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen

import vlc

VLC_CORE_PATH = r"C:\Program Files\VideoLAN\VLC\libvlccore.dll"

VLC_VAR_ADDRESS = 0x0070


class VLCValue(ctypes.Union):

    _fields_ = [
        ("p_address", ctypes.c_void_p),
        ("i_int", ctypes.c_int64),
        ("f_float", ctypes.c_float),
        ("b_bool", ctypes.c_bool)
    ]


try:

    vlc_core = ctypes.CDLL(
        VLC_CORE_PATH
    )

    vlc_core.vlc_http_cookies_store.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p
    ]

    vlc_core.vlc_http_cookies_store.restype = ctypes.c_bool

    vlc_core.var_GetChecked.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.POINTER(VLCValue)
    ]

    vlc_core.var_GetChecked.restype = ctypes.c_int

    print(
        "VLC cookie support initialized."
    )

except Exception as error:

    vlc_core = None

    print(
        "VLC cookie support unavailable:"
    )

    print(
        error
    )


from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QDialog,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QComboBox
)

from PySide6.QtCore import (
    Qt,
    QTimer,
    QSize,
    QObject,
    QEvent
)

from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QPainter,
    QPen,
    QFont
)


def resource_path(relative_path):

    if (
        getattr(sys, "frozen", False)
        and hasattr(sys, "_MEIPASS")
    ):

        base_dir = sys._MEIPASS

    else:

        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

    return os.path.join(
        base_dir,
        relative_path
    )


if getattr(sys, "frozen", False):

    DATA_DIR = os.path.dirname(
        sys.executable
    )

else:

    DATA_DIR = os.path.dirname(
        os.path.abspath(__file__)
    )


CHANNELS_FILE = os.path.join(
    DATA_DIR,
    "channels.json"
)

CHANNEL_LIST_FILE = os.path.join(
    DATA_DIR,
    "channel_list.json"
)

CHANNEL_LOGOS_DIR = os.path.join(
    DATA_DIR,
    "channel_logos"
)

os.makedirs(
    CHANNEL_LOGOS_DIR,
    exist_ok=True
)


LOGO_PATH = resource_path(
    "tnu.png"
)

WINDOW_ICON_PATH = resource_path(
    "Window.png"
)

RECORD_ICON_PATH = resource_path(
    "Record.png"
)


TNU_STREAM = "https://tinyurl.com/canal5uy"


# ---------------------------------------------------------
# GENERIC STREAM COOKIE / TOKEN
# ---------------------------------------------------------

STREAM_COOKIE = os.environ.get(
    "ZAP_STREAM_COOKIE",
    ""
).strip()

print(
    "STREAM TOKEN AVAILABLE:",
    bool(STREAM_COOKIE)
)

STREAM_COOKIE_PATH = os.environ.get(
    "ZAP_STREAM_COOKIE_PATH",
    "/"
).strip()


# ---------------------------------------------------------
# VERA / ANTEL TV SESSION TOKEN
# ---------------------------------------------------------
#
# This is the already obtained token_sesion.
#
# It is intentionally NOT hardcoded here.
#
# Windows:
#
# $env:ZAP_VERA_TOKEN="YOUR_TOKEN_HERE"
#
# The token is then inherited by main.py / dev.py.
# ---------------------------------------------------------

VERA_SESSION_TOKEN = os.environ.get(
    "ZAP_VERA_TOKEN",
    ""
).strip()

VERA_SETUP_URL = (
    "https://veratv-be.vera.com.uy/api/setup"
)

CANAL6_PUBLIC_ID = "2s6pn"

CANAL6_BASE_URL_PART = (
    "auth_D_Canal6_Durazno"
)


print(
    "VERA SESSION TOKEN AVAILABLE:",
    bool(VERA_SESSION_TOKEN)
)


def configure_vlc_cookie(
    player_object,
    cookie_value,
    url
):

    if (
        vlc_core is None
        or not cookie_value
        or player_object is None
    ):

        return False

    try:

        parsed_url = urlparse(
            str(url).strip()
        )

        host = parsed_url.hostname

        if not host:

            print(
                "Could not determine cookie host."
            )

            return False

        player_ptr = (
            player_object._as_parameter_
        )

        value = VLCValue()

        result = vlc_core.var_GetChecked(
            player_ptr,
            b"http-cookies",
            VLC_VAR_ADDRESS,
            ctypes.byref(value)
        )

        if result != 0:

            print(
                "Could not get VLC HTTP cookie jar."
            )

            return False

        cookie_jar = value.p_address

        if not cookie_jar:

            print(
                "VLC HTTP cookie jar is unavailable."
            )

            return False

        cookie = cookie_value

        if "=" not in cookie:

            cookie = (
                f"vxttoken={cookie}"
            )

        cookie = (
            f"{cookie}; "
            f"Path={STREAM_COOKIE_PATH}; "
            "Secure"
        )

        stored = vlc_core.vlc_http_cookies_store(
            cookie_jar,
            cookie.encode("utf-8"),
            host.encode("utf-8"),
            STREAM_COOKIE_PATH.encode("utf-8")
        )

        print(
            "VLC stream cookie stored:",
            bool(stored),
            "host:",
            host
        )

        return bool(stored)

    except Exception as error:

        print(
            "Could not configure VLC cookie:"
        )

        print(
            error
        )

        return False


# ---------------------------------------------------------
# VXT TOKEN URL
# ---------------------------------------------------------

def apply_stream_token(url):

    """
    Antel protected streams may use the token directly
    inside the URL path:

        /out,vxttoken=TOKEN/u/...

    The channel database keeps the normal URL.
    The token is added only when VLC opens the stream.

    Channels that do not use /out/ are left unchanged.
    """

    url = str(
        url
    ).strip()

    if not STREAM_COOKIE:

        return url

    if "vxttoken=" in url:

        return url

    if "/out/" not in url:

        return url

    token = STREAM_COOKIE.strip()

    if "=" in token:

        token = token.split(
            "=",
            1
        )[1].strip()

    if not token:

        return url

    tokenized_url = url.replace(
        "/out/",
        f"/out,vxttoken={token}/",
        1
    )

    print(
        "VXT token applied to stream URL."
    )

    return tokenized_url


# ---------------------------------------------------------
# VERA SIGNED URL RESOLVER
# ---------------------------------------------------------

def resolve_vera_stream_url(
    channel,
    fallback_url
):

    """
    Canal 6 Durazno uses Vera's setup endpoint.

    The channel database contains the normal HLS URL:

        https://livedelta.cdn.antel.net.uy/out/u/...

    Vera's setup endpoint returns a fresh signed URL:

        /out,vxttoken=TOKEN/u/...

    We obtain that signed URL immediately before playback
    or recording.

    The session token is never placed into the channel URL.
    """

    original_url = str(
        fallback_url
    ).strip()

    if not original_url:

        return original_url

    if not VERA_SESSION_TOKEN:

        print(
            "VERA_SESSION_TOKEN is not configured."
        )

        return apply_stream_token(
            original_url
        )

    if not isinstance(
        channel,
        dict
    ):

        return apply_stream_token(
            original_url
        )

    channel_url = str(
        channel.get(
            "url",
            ""
        )
    ).strip()

    channel_name = str(
        channel.get(
            "name",
            ""
        )
    ).strip().lower()

    is_canal6 = (
        CANAL6_BASE_URL_PART.lower()
        in channel_url.lower()
        or CANAL6_BASE_URL_PART.lower()
        in original_url.lower()
        or "canal 6 durazno"
        in channel_name
        or "canal6 durazno"
        in channel_name
    )

    if not is_canal6:

        return apply_stream_token(
            original_url
        )

    try:

        query = urlencode(
            {
                "token": VERA_SESSION_TOKEN,
                "public_id": CANAL6_PUBLIC_ID
            }
        )

        setup_url = (
            f"{VERA_SETUP_URL}?{query}"
        )

        print(
            "Requesting fresh Vera setup URL..."
        )

        request = Request(
            setup_url,
            headers={
                "Accept": (
                    "application/json, "
                    "text/plain, */*"
                ),
                "Origin": (
                    "https://anteltv.com.uy"
                ),
                "Referer": (
                    "https://anteltv.com.uy/"
                ),
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/153.0.0.0 "
                    "Safari/537.36"
                )
            }
        )

        with urlopen(
            request,
            timeout=10
        ) as response:

            response_bytes = response.read()

        response_text = response_bytes.decode(
            "utf-8"
        )

        setup_data = json.loads(
            response_text
        )

        signed_url = (
            (
                setup_data.get(
                    "url"
                ) or {}
            ).get(
                "suggested"
            ) or {}
        ).get(
            "url"
        )

        if signed_url:

            signed_url = str(
                signed_url
            ).strip()

            print(
                "Fresh Vera signed URL obtained."
            )

            print(
                "Vera stream URL:",
                signed_url
            )

            return signed_url

        print(
            "Vera setup did not return "
            "url.suggested.url."
        )

        return apply_stream_token(
            original_url
        )

    except Exception as error:

        print(
            "Could not obtain Vera signed URL:"
        )

        print(
            error
        )

        print(
            "Falling back to normal stream URL."
        )

        return apply_stream_token(
            original_url
        )


def resolve_stream_url(
    channel,
    url
):

    """
    Resolves protected streams before VLC opens them.

    Canal 6 Durazno:
        Vera setup -> fresh signed HLS URL.

    Other Antel protected streams:
        normal ZAP_STREAM_COOKIE handling.

    Everything else:
        unchanged.
    """

    return resolve_vera_stream_url(
        channel,
        url
    )


COUNTRIES = [
    "Afghanistan",
    "Albania",
    "Algeria",
    "Andorra",
    "Angola",
    "Antigua and Barbuda",
    "Argentina",
    "Armenia",
    "Australia",
    "Austria",
    "Azerbaijan",
    "Bahamas",
    "Bahrain",
    "Bangladesh",
    "Barbados",
    "Belarus",
    "Belgium",
    "Belize",
    "Benin",
    "Bhutan",
    "Bolivia",
    "Bosnia and Herzegovina",
    "Botswana",
    "Brazil",
    "Brunei",
    "Bulgaria",
    "Burkina Faso",
    "Cabo Verde",
    "Cambodia",
    "Cameroon",
    "Canada",
    "Central African Republic",
    "Chad",
    "Chile",
    "China",
    "Colombia",
    "Comoros",
    "Congo, Democratic Republic of the",
    "Congo, Republic of the",
    "Costa Rica",
    "Croatia",
    "Cuba",
    "Cyprus",
    "Czechia",
    "Denmark",
    "Djibouti",
    "Dominica",
    "Dominican Republic",
    "Ecuador",
    "Egypt",
    "El Salvador",
    "Equatorial Guinea",
    "Eritrea",
    "Eswatini",
    "Ethiopia",
    "Fiji",
    "Finland",
    "France",
    "Gabon",
    "Gambia",
    "Georgia",
    "Germany",
    "Ghana",
    "Greece",
    "Grenada",
    "Guatemala",
    "Guinea",
    "Guinea-Bissau",
    "Guyana",
    "Haiti",
    "Honduras",
    "Hungary",
    "Iceland",
    "India",
    "Indonesia",
    "Iran",
    "Iraq",
    "Ireland",
    "Italy",
    "Jamaica",
    "Japan",
    "Kazakhstan",
    "Kenya",
    "Kiribati",
    "Kuwait",
    "Laos",
    "Latvia",
    "Lebanon",
    "Lesotho",
    "Liberia",
    "Libya",
    "Liechtenstein",
    "Lithuania",
    "Madagascar",
    "Malawi",
    "Malaysia",
    "Maldives",
    "Mali",
    "Malta",
    "Marshall Islands",
    "Mauritania",
    "Mauritius",
    "Mexico",
    "Micronesia",
    "Moldova",
    "Monaco",
    "Mongolia",
    "Montenegro",
    "Morocco",
    "Mozambique",
    "Myanmar",
    "Namibia",
    "Nauru",
    "Nepal",
    "Netherlands",
    "New Zealand",
    "Nicaragua",
    "Niger",
    "Nigeria",
    "North Korea",
    "North Macedonia",
    "Norway",
    "Oman",
    "Pakistan",
    "Palau",
    "Palestine",
    "Panama",
    "Papua New Guinea",
    "Paraguay",
    "Peru",
    "Philippines",
    "Portugal",
    "Qatar",
    "Romania",
    "Russia",
    "Rwanda",
    "Saint Kitts and Nevis",
    "Saint Lucia",
    "Saint Vincent and the Grenadines",
    "Samoa",
    "San Marino",
    "Sao Tome and Principe",
    "Saudi Arabia",
    "Senegal",
    "Serbia",
    "Seychelles",
    "Sierra Leone",
    "Singapore",
    "Slovakia",
    "Slovenia",
    "Somalia",
    "South Africa",
    "South Korea",
    "South Sudan",
    "Spain",
    "Sri Lanka",
    "Sudan",
    "Suriname",
    "Sweden",
    "Switzerland",
    "Syria",
    "Tajikistan",
    "Tanzania",
    "Thailand",
    "Timor-Leste",
    "Togo",
    "Tonga",
    "Trinidad and Tobago",
    "Tunisia",
    "Turkey",
    "Tuvalu",
    "Uganda",
    "Ukraine",
    "United Arab Emirates",
    "United Kingdom",
    "United States",
    "Uruguay",
    "Uzbekistan",
    "Vanuatu",
    "Vatican City",
    "Venezuela",
    "Vietnam",
    "Yemen",
    "Zambia",
    "Zimbabwe"
]


channels = {
    "5": {
        "name": "Televisión Nacional Uruguay",
        "country": "Uruguay",
        "url": TNU_STREAM,
        "logo": LOGO_PATH
    }
}


custom_channel_list = []


def load_channels():

    global channels

    if not os.path.exists(
        CHANNELS_FILE
    ):

        return

    try:

        with open(
            CHANNELS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            saved_channels = json.load(
                file
            )

        if not isinstance(
            saved_channels,
            dict
        ):

            return

        loaded_channels = {}

        for number, data in saved_channels.items():

            if not isinstance(
                data,
                dict
            ):

                continue

            if "name" not in data:

                continue

            if "url" not in data:

                continue

            loaded_channels[
                str(number)
            ] = data

        channels = loaded_channels

    except Exception as error:

        print(
            "Could not load channels.json:"
        )

        print(
            error
        )


def save_channels():

    try:

        if os.path.exists(CHANNELS_FILE):

            os.system(
                f'attrib -H "{CHANNELS_FILE}"'
            )

        with open(
            CHANNELS_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                channels,
                file,
                indent=4,
                ensure_ascii=False
            )

    except Exception as error:

        print(
            "Could not save channels:"
        )

        print(
            error
        )


def load_custom_channel_list():

    global custom_channel_list

    if not channels:

        custom_channel_list = []

        return

    if not os.path.exists(
        CHANNEL_LIST_FILE
    ):

        custom_channel_list = sorted(
            channels.keys(),
            key=lambda x: int(x)
        )

        return

    try:

        with open(
            CHANNEL_LIST_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            saved_list = json.load(
                file
            )

        if not isinstance(
            saved_list,
            list
        ):

            raise ValueError(
                "Invalid channel list format."
            )

        custom_channel_list = []

        for number in saved_list:

            number = str(
                number
            )

            if (
                number in channels
                and number not in custom_channel_list
            ):

                custom_channel_list.append(
                    number
                )

        for number in sorted(
            channels.keys(),
            key=lambda x: int(x)
        ):

            if number not in custom_channel_list:

                custom_channel_list.append(
                    number
                )

        custom_channel_list.sort(
            key=lambda x: int(x)
        )

    except Exception as error:

        print(
            "Could not load custom channel list:"
        )

        print(
            error
        )

        custom_channel_list = sorted(
            channels.keys(),
            key=lambda x: int(x)
        )


def save_custom_channel_list():

    global custom_channel_list

    custom_channel_list = [
        str(number)
        for number in custom_channel_list
        if str(number) in channels
    ]

    custom_channel_list.sort(
        key=lambda x: int(x)
    )

    try:

        if os.path.exists(CHANNEL_LIST_FILE):

            os.system(
                f'attrib -H "{CHANNEL_LIST_FILE}"'
            )

        with open(
            CHANNEL_LIST_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                custom_channel_list,
                file,
                indent=4,
                ensure_ascii=False
            )

    except Exception as error:

        print(
            "Could not save custom channel list:"
        )

        print(
            error
        )


load_channels()
load_custom_channel_list()


app = QApplication(
    sys.argv
)

app.setApplicationName(
    "Zap"
)

app.setApplicationDisplayName(
    "Zap"
)

app.setOrganizationName(
    "ZAP"
)

app.setStyle(
    "Fusion"
)

if sys.platform.startswith(
    "win"
):

    try:

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ZAP.Zap"
        )

    except Exception:

        pass


if os.path.exists(
    WINDOW_ICON_PATH
):

    app.setWindowIcon(
        QIcon(
            WINDOW_ICON_PATH
        )
    )


def handle_unhandled_exception(
    exc_type,
    exc_value,
    exc_traceback
):

    if issubclass(
        exc_type,
        KeyboardInterrupt
    ):

        sys.__excepthook__(
            exc_type,
            exc_value,
            exc_traceback
        )

        return

    print(
        "Unhandled exception:"
    )

    print(
        exc_type,
        exc_value
    )

    try:

        QMessageBox.critical(
            None,
            "Zap",
            (
                "An unexpected error occurred.\n\n"
                f"{exc_value}"
            )
        )

    except Exception:

        pass


sys.excepthook = handle_unhandled_exception


app.setStyleSheet("""
    QWidget {
        font-family: "Segoe UI";
        font-size: 9pt;
    }

    QMainWindow {
        background-color: #f0f0f0;
    }

    QMenuBar {
        background-color: #f2f2f2;
        color: #111111;
        border-bottom: 1px solid #c8c8c8;
        padding: 1px;
    }

    QMenuBar::item {
        background-color: transparent;
        padding: 3px 8px;
    }

    QMenuBar::item:selected {
        background-color: #dbeeff;
        border: 1px solid #9ac7ef;
    }

    QMenu {
        background-color: #ffffff;
        color: #111111;
        border: 1px solid #999999;
    }

    QMenu::item {
        padding: 4px 24px 4px 20px;
    }

    QMenu::item:selected {
        background-color: #dceeff;
        color: #000000;
    }

    QFrame#videoFrame {
        background-color: #050505;
        border: none;
    }

    QPushButton {
        background-color: #f0f0f0;
        color: #111111;
        border: 1px solid #999999;
        border-radius: 2px;
        padding: 3px 8px;
        min-height: 22px;
    }

    QPushButton:hover {
        background-color: #e4e4e4;
        border: 1px solid #777777;
    }

    QPushButton:pressed {
        background-color: #d4d4d4;
        border: 1px solid #666666;
    }

    QPushButton:disabled {
        background-color: #eeeeee;
        color: #888888;
        border: 1px solid #c0c0c0;
    }

    QListWidget {
        background-color: #ffffff;
        color: #111111;
        border: 1px solid #999999;
        font-size: 9pt;
    }

    QListWidget::item {
        padding: 0px;
        margin: 0px;
        border: none;
    }

    QComboBox {
        background-color: #ffffff;
        color: #111111;
        border: 1px solid #999999;
        padding: 3px 6px;
    }

    QComboBox:hover {
        border: 1px solid #777777;
    }

    QComboBox QAbstractItemView {
        background-color: #ffffff;
        color: #111111;
        border: 1px solid #999999;
        selection-background-color: #dbeeff;
        selection-color: #111111;
    }
""")


window = QMainWindow()

window.setWindowTitle(
    "Zap"
)

window.resize(
    900,
    600
)

window.setMinimumSize(
    700,
    500
)


if os.path.exists(
    WINDOW_ICON_PATH
):

    window.setWindowIcon(
        QIcon(
            WINDOW_ICON_PATH
        )
    )


menu_bar = window.menuBar()

options_action = menu_bar.addAction(
    "Options"
)

help_action = menu_bar.addAction(
    "Help"
)

add_channel_action = menu_bar.addAction(
    "Add Channel..."
)


central = QWidget()

layout = QVBoxLayout(
    central
)

layout.setContentsMargins(
    0,
    0,
    0,
    0
)

layout.setSpacing(
    0
)


video_frame = QFrame()

video_frame.setObjectName(
    "videoFrame"
)


video_surface = QWidget(
    video_frame
)

video_surface.setAttribute(
    Qt.WA_NativeWindow,
    True
)

video_surface.setStyleSheet("""
    background-color: #050505;
    border: none;
""")


video_placeholder = QLabel(
    video_surface
)

video_placeholder.setAlignment(
    Qt.AlignCenter
)

video_placeholder.setStyleSheet("""
    background-color: #050505;
    color: #eeeeee;
    border: none;
    font-family: "Segoe UI";
    font-size: 34px;
    font-weight: normal;
""")


if channels:

    video_placeholder.setText(
        "Select a channel!"
    )

else:

    video_placeholder.setText(
        "Add a channel!"
    )


def resize_video_surface():

    video_surface.setGeometry(
        0,
        0,
        video_frame.width(),
        video_frame.height()
    )

    video_placeholder.setGeometry(
        0,
        0,
        video_surface.width(),
        video_surface.height()
    )


layout.addWidget(
    video_frame,
    1
)


class ChannelNumberOverlay(QLabel):

    def __init__(
        self,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.setAttribute(
            Qt.WA_TransparentForMouseEvents,
            True
        )

        self.setAlignment(
            Qt.AlignRight
            | Qt.AlignTop
        )

        self.setStyleSheet(
            "background: transparent; border: none;"
        )

        self.hide()

    def paintEvent(
        self,
        event
    ):

        if not self.text():

            return

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        font = QFont(
            "Segoe UI",
            42,
            QFont.Bold
        )

        painter.setFont(
            font
        )

        rect = self.rect().adjusted(
            6,
            6,
            -10,
            -6
        )

        painter.setPen(
            QPen(
                Qt.black,
                8,
                Qt.SolidLine,
                Qt.RoundCap,
                Qt.RoundJoin
            )
        )

        painter.drawText(
            rect,
            Qt.AlignRight
            | Qt.AlignTop,
            self.text()
        )

        painter.setPen(
            QPen(
                Qt.white,
                1
            )
        )

        painter.drawText(
            rect,
            Qt.AlignRight
            | Qt.AlignTop,
            self.text()
        )


channel_number_overlay = ChannelNumberOverlay(
    video_frame
)

channel_number_overlay.setGeometry(
    0,
    0,
    video_frame.width(),
    90
)


def resize_channel_number_overlay():

    channel_number_overlay.setGeometry(
        0,
        0,
        video_frame.width(),
        90
    )


def show_channel_number_input():

    channel_number_overlay.setText(
        window.channel_buffer
    )

    channel_number_overlay.show()

    channel_number_overlay.raise_()


def hide_channel_number_input():

    channel_number_overlay.clear()

    channel_number_overlay.hide()


info_bar = QWidget()

info_bar.setFixedHeight(
    48
)

info_bar.setStyleSheet("""
    background-color: white;
    border: none;
""")


info_layout = QHBoxLayout(
    info_bar
)

info_layout.setContentsMargins(
    8,
    0,
    0,
    0
)

info_layout.setSpacing(
    8
)


logo = QLabel()

logo.setFixedSize(
    34,
    34
)

logo.setAlignment(
    Qt.AlignCenter
)

logo.setStyleSheet("""
    background-color: transparent;
    border: none;
""")


channel_text = QWidget()

channel_text.setStyleSheet("""
    background-color: transparent;
    border: none;
""")


channel_text_layout = QVBoxLayout(
    channel_text
)

channel_text_layout.setContentsMargins(
    0,
    0,
    0,
    0
)

channel_text_layout.setSpacing(
    0
)


channel_name = QLabel()

channel_name.setAlignment(
    Qt.AlignLeft | Qt.AlignVCenter
)

channel_name.setStyleSheet("""
    background-color: transparent;
    color: #111111;
    border: none;
    font-family: "Segoe UI";
    font-size: 10pt;
    font-weight: bold;
""")


country = QLabel()

country.setAlignment(
    Qt.AlignLeft | Qt.AlignVCenter
)

country.setStyleSheet("""
    background-color: transparent;
    color: #666666;
    border: none;
    font-family: "Segoe UI";
    font-size: 9pt;
""")


channel_text_layout.addWidget(
    channel_name
)

channel_text_layout.addWidget(
    country
)


info_layout.addWidget(
    logo
)

info_layout.addWidget(
    channel_text
)

info_layout.addStretch()


record_button = QPushButton(
    info_bar
)

record_button.setFixedSize(
    34,
    34
)

record_button.setCursor(
    Qt.PointingHandCursor
)

record_button.setToolTip(
    "Record"
)


def load_record_icon():

    if not os.path.exists(
        RECORD_ICON_PATH
    ):

        print(
            "Record icon not found:",
            RECORD_ICON_PATH
        )

        return

    record_pixmap = QPixmap(
        RECORD_ICON_PATH
    )

    if record_pixmap.isNull():

        print(
            "Could not load Record.png:",
            RECORD_ICON_PATH
        )

        return

    record_button.setIcon(
        QIcon(
            record_pixmap
        )
    )

    record_button.setIconSize(
        QSize(
            30,
            30
        )
    )

    record_button.update()

    record_button.raise_()


load_record_icon()


record_button.hide()


channel_number = QLabel()

channel_number.setAlignment(
    Qt.AlignCenter
)

channel_number.setFixedSize(
    75,
    48
)

channel_number.setStyleSheet("""
    background-color: #eeeeee;
    color: #222222;
    border: none;
    border-left: 1px solid #bcbcbc;
    font-family: "Segoe UI";
    font-size: 16pt;
    font-weight: bold;
""")


info_layout.addWidget(
    record_button
)

info_layout.addWidget(
    channel_number
)


info_bar.hide()

layout.addWidget(
    info_bar
)

window.setCentralWidget(
    central
)


try:

    vlc_instance = vlc.Instance(
        "--no-video-title-show",
        "--http-forward-cookies"
    )

    player = vlc_instance.media_player_new()

    print(
        "VLC initialized successfully."
    )

except Exception as error:

    vlc_instance = None
    player = None

    print(
        "VLC initialization error:"
    )

    print(
        error
    )


def configure_live_media(
    media,
    url,
    channel
):

    normalized_url = (
        url.strip().lower()
    )

    media.add_option(
        ":network-caching=1000"
    )

    if (
        normalized_url.startswith("http://")
        or normalized_url.startswith("https://")
    ):

        if channel is not None:

            if (
                channel.get("url")
                == TNU_STREAM
            ):

                media.add_option(
                    ":http-referrer=https://tinyurl.com/"
                )

    elif normalized_url.startswith(
        "rtsp://"
    ):

        print(
            "Detected live protocol: RTSP"
        )

    elif normalized_url.startswith(
        "rtp://"
    ):

        print(
            "Detected live protocol: RTP"
        )

    elif normalized_url.startswith(
        "udp://"
    ):

        print(
            "Detected live protocol: UDP"
        )

    elif normalized_url.startswith(
        "rtmp://"
    ):

        print(
            "Detected live protocol: RTMP"
        )


def update_empty_state():

    if recording:

        stop_recording()

    if player is not None:

        try:

            player.stop()

        except Exception:

            pass

    info_bar.hide()

    record_button.hide()

    hide_channel_number_input()

    logo.clear()

    channel_name.clear()

    country.clear()

    channel_number.clear()

    video_surface.lower()

    video_placeholder.setText(
        "Add a channel!"
    )

    video_placeholder.show()

    video_placeholder.raise_()


def update_channel_info(
    number,
    channel
):

    channel_name.setText(
        channel.get(
            "name",
            "Unknown channel"
        )
    )

    country.setText(
        channel.get(
            "country",
            "Unknown"
        )
    )

    channel_number.setText(
        str(number).zfill(2)
    )

    logo.clear()

    logo_path = str(
        channel.get(
            "logo",
            ""
        )
    ).strip()

    if (
        not logo_path
        or not os.path.exists(
            logo_path
        )
    ):

        logo_path = LOGO_PATH

    pixmap = QPixmap(
        logo_path
    )

    if pixmap.isNull():

        if logo_path != LOGO_PATH:

            pixmap = QPixmap(
                LOGO_PATH
            )

    if not pixmap.isNull():

        pixmap = pixmap.scaled(
            34,
            34,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        logo.setPixmap(
            pixmap
        )


record_instance = None
record_player = None

recording = False

recording_file = ""
recording_temp_file = ""

current_record_url = ""
current_record_channel = None

recording_finish_timer = None


def update_record_button_style():

    if recording:

        record_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 2px solid #777777;
                border-radius: 4px;
                padding: 0px;
                min-height: 0px;
            }

            QPushButton:hover {
                background-color: #eeeeee;
                border: 2px solid #555555;
            }

            QPushButton:pressed {
                background-color: #dddddd;
                border: 2px solid #444444;
            }
        """)

        record_button.setToolTip(
            "Stop recording"
        )

    else:

        record_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 2px solid transparent;
                border-radius: 4px;
                padding: 0px;
                min-height: 0px;
            }

            QPushButton:hover {
                background-color: #eeeeee;
                border: 2px solid transparent;
            }

            QPushButton:pressed {
                background-color: #dddddd;
                border: 2px solid transparent;
            }
        """)

        record_button.setToolTip(
            "Record"
        )

    record_button.raise_()
    record_button.update()


def create_recording_media(
    url,
    output_file
):

    if record_instance is None:

        raise RuntimeError(
            "Recording VLC instance is not available."
        )

    media = record_instance.media_new(
        url
    )

    media.add_option(
        ":network-caching=1000"
    )

    if (
        url.strip()
        == TNU_STREAM
    ):

        media.add_option(
            ":http-referrer=https://tinyurl.com/"
        )

    absolute_output = os.path.abspath(
        output_file
    )

    escaped_output = (
        absolute_output
        .replace(
            "\\",
            "/"
        )
        .replace(
            "'",
            "\\'"
        )
    )

    sout = (
        "#std{"
        "access=file,"
        "mux=mp4,"
        f"dst='{escaped_output}'"
        "}"
    )

    media.add_option(
        f":sout={sout}"
    )

    media.add_option(
        ":sout-keep"
    )

    return media


def start_recording():

    global record_instance
    global record_player
    global recording
    global recording_file
    global recording_temp_file
    global current_record_url
    global current_record_channel

    if recording:

        return

    if player is None:

        QMessageBox.warning(
            window,
            "Recording",
            "VLC is not available."
        )

        return

    if not channel_number.text():

        QMessageBox.warning(
            window,
            "Recording",
            "Select a channel first."
        )

        return

    current_number = (
        channel_number.text()
        .strip()
    )

    try:

        current_number = str(
            int(current_number)
        )

    except ValueError:

        return

    if current_number not in channels:

        return

    current_channel = channels[
        current_number
    ]

    url = str(
        current_channel.get(
            "url",
            ""
        )
    ).strip()

    if not url:

        QMessageBox.warning(
            window,
            "Recording",
            "The current channel has no stream URL."
        )

        return

    # Resolve a fresh signed URL when required.
    url = resolve_stream_url(
        current_channel,
        url
    )

    suggested_name = (
        f"Zap_CH{current_number.zfill(2)}_"
        f"{current_channel.get('name', 'Channel')}"
        ".mp4"
    )

    output_file, _ = QFileDialog.getSaveFileName(
        window,
        "Save Recording",
        suggested_name,
        "MP4 Video (*.mp4)"
    )

    if not output_file:

        return

    if not output_file.lower().endswith(
        ".mp4"
    ):

        output_file += ".mp4"

    temp_file = os.path.join(
        tempfile.gettempdir(),
        (
            "Zap_"
            f"{os.getpid()}_"
            f"{id(window)}_"
            "recording.part.mp4"
        )
    )

    if os.path.exists(
        temp_file
    ):

        try:

            os.remove(
                temp_file
            )

        except Exception:

            pass

    try:

        record_instance = vlc.Instance(
            "--no-video-title-show",
            "--http-forward-cookies"
        )

        record_player = (
            record_instance.media_player_new()
        )

        media = create_recording_media(
            url,
            temp_file
        )

        record_player.set_media(
            media
        )

        result = record_player.play()

        if result == -1:

            raise RuntimeError(
                "VLC could not start recording."
            )

        recording_file = output_file

        recording_temp_file = temp_file

        current_record_url = url

        current_record_channel = current_channel

        recording = True

        update_record_button_style()

    except Exception as error:

        print(
            "Could not start recording:"
        )

        print(
            error
        )

        recording = False

        recording_file = ""

        recording_temp_file = ""

        if record_player is not None:

            try:

                record_player.stop()

            except Exception:

                pass

            try:

                record_player.release()

            except Exception:

                pass

        record_player = None

        if record_instance is not None:

            try:

                record_instance.release()

            except Exception:

                pass

        record_instance = None

        update_record_button_style()

        try:

            if os.path.exists(
                temp_file
            ):

                os.remove(
                    temp_file
                )

        except Exception:

            pass

        QMessageBox.critical(
            window,
            "Recording",
            f"Could not start recording:\n\n{error}"
        )


def finalize_recording():

    global record_instance
    global record_player
    global recording_file
    global recording_temp_file
    global current_record_url
    global current_record_channel
    global recording_finish_timer

    saved_file = recording_file

    temp_file = recording_temp_file

    if record_player is not None:

        try:

            record_player.stop()

        except Exception:

            pass

        try:

            record_player.release()

        except Exception:

            pass

        record_player = None

    if record_instance is not None:

        try:

            record_instance.release()

        except Exception:

            pass

        record_instance = None

    temp_size = 0

    if (
        temp_file
        and os.path.exists(
            temp_file
        )
    ):

        try:

            temp_size = os.path.getsize(
                temp_file
            )

        except Exception:

            temp_size = 0

    if (
        temp_file
        and saved_file
        and temp_size > 1024
    ):

        try:

            if os.path.exists(
                saved_file
            ):

                os.remove(
                    saved_file
                )

            os.replace(
                temp_file,
                saved_file
            )

            final_size = os.path.getsize(
                saved_file
            )

            if final_size > 1024:

                QMessageBox.information(
                    window,
                    "Recording",
                    "Recording saved successfully."
                )

        except Exception as error:

            print(
                "Could not finalize MP4:"
            )

            print(
                error
            )

            QMessageBox.warning(
                window,
                "Recording",
                "Could not save MP4."
            )

    else:

        if (
            temp_file
            and os.path.exists(
                temp_file
            )
        ):

            try:

                os.remove(
                    temp_file
                )

            except Exception:

                pass

        QMessageBox.warning(
            window,
            "Recording",
            "Could not save MP4."
        )

    recording_file = ""

    recording_temp_file = ""

    current_record_url = ""

    current_record_channel = None

    recording_finish_timer = None


def stop_recording():

    global recording
    global recording_finish_timer

    if not recording:

        return

    recording = False

    update_record_button_style()

    if record_player is not None:

        try:

            record_player.stop()

        except Exception:

            pass

    recording_finish_timer = QTimer.singleShot(
        1500,
        finalize_recording
    )


def record_button_clicked():

    if recording:

        stop_recording()

    else:

        start_recording()


record_button.clicked.connect(
    record_button_clicked
)


def play_channel(
    number
):

    global current_record_url
    global current_record_channel

    try:

        number = str(
            int(
                str(number).strip()
            )
        )

    except ValueError:

        number = str(
            number
        )

    hide_channel_number_input()

    if not channels:

        update_empty_state()

        return

    if number not in channels:

        print(
            "Channel does not exist:",
            number
        )

        update_empty_state()

        return

    if recording:

        stop_recording()

    channel = channels[
        number
    ]

    if player is None:

        update_empty_state()

        return

    update_channel_info(
        number,
        channel
    )

    video_placeholder.hide()

    video_surface.raise_()

    info_bar.show()

    record_button.show()
    record_button.raise_()

    url = str(
        channel.get(
            "url",
            ""
        )
    ).strip()

    if not url:

        update_empty_state()

        return

    # -----------------------------------------------------
    # Resolve protected streams.
    #
    # Canal 6 Durazno:
    #
    # normal URL
    #      ↓
    # Vera /api/setup
    #      ↓
    # fresh /out,vxttoken=.../ URL
    #      ↓
    # VLC
    #
    # Other channels continue using the existing
    # ZAP_STREAM_COOKIE mechanism.
    # -----------------------------------------------------

    url = resolve_stream_url(
        channel,
        url
    )

    current_record_url = url

    current_record_channel = channel

    try:

        media = vlc_instance.media_new(
            url
        )

    except Exception as error:

        print(
            "Could not create VLC media:"
        )

        print(
            error
        )

        update_empty_state()

        return

    configure_live_media(
        media,
        url,
        channel
    )

    # No Cookie header is added here.
    # Antel's vxttoken is part of the URL path.

    player.set_media(
        media
    )

    if sys.platform.startswith(
        "win"
    ):

        player.set_hwnd(
            int(
                video_surface.winId()
            )
        )

    resize_video_surface()

    try:

        player.play()

    except Exception as error:

        print(
            "VLC playback error:"
        )

        print(
            error
        )


def manage_channel(
    number,
    parent
):

    number = str(
        number
    )

    if number not in channels:

        return None

    channel = channels[
        number
    ]

    dialog = QDialog(
        parent
    )

    dialog.setWindowTitle(
        "Manage Channel"
    )

    dialog.setFixedSize(
        430,
        235
    )

    if os.path.exists(
        WINDOW_ICON_PATH
    ):

        dialog.setWindowIcon(
            QIcon(
                WINDOW_ICON_PATH
            )
        )

    form = QFormLayout(
        dialog
    )

    form.setContentsMargins(
        12,
        12,
        12,
        12
    )

    form.setSpacing(
        7
    )

    number_edit = QLineEdit(
        number
    )

    name_edit = QLineEdit(
        channel.get(
            "name",
            ""
        )
    )

    country_edit = QComboBox()

    country_edit.addItems(
        COUNTRIES
    )

    country_value = str(
        channel.get(
            "country",
            ""
        )
    ).strip()

    country_index = country_edit.findText(
        country_value
    )

    if country_index >= 0:

        country_edit.setCurrentIndex(
            country_index
        )

    elif country_value:

        country_edit.addItem(
            country_value
        )

        country_edit.setCurrentIndex(
            country_edit.count() - 1
        )

    country_edit.setMaxVisibleItems(
        12
    )

    url_edit = QLineEdit(
        channel.get(
            "url",
            ""
        )
    )

    logo_edit = QLineEdit(
        channel.get(
            "logo",
            ""
        )
    )

    logo_edit.setReadOnly(
        True
    )

    browse_button = QPushButton(
        "Browse..."
    )

    logo_widget = QWidget()

    logo_layout = QHBoxLayout(
        logo_widget
    )

    logo_layout.setContentsMargins(
        0,
        0,
        0,
        0
    )

    logo_layout.addWidget(
        logo_edit
    )

    logo_layout.addWidget(
        browse_button
    )

    def browse_logo():

        file_path, _ = QFileDialog.getOpenFileName(
            dialog,
            "Select channel logo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )

        if file_path:

            logo_edit.setText(
                file_path
            )

    browse_button.clicked.connect(
        browse_logo
    )

    buttons = QDialogButtonBox(
        QDialogButtonBox.Save
        | QDialogButtonBox.Cancel
    )

    form.addRow(
        "Channel number:",
        number_edit
    )

    form.addRow(
        "Channel name:",
        name_edit
    )

    form.addRow(
        "Country:",
        country_edit
    )

    form.addRow(
        "Stream URL:",
        url_edit
    )

    form.addRow(
        "Logo:",
        logo_widget
    )

    form.addRow(
        buttons
    )

    buttons.accepted.connect(
        dialog.accept
    )

    buttons.rejected.connect(
        dialog.reject
    )

    if dialog.exec() != QDialog.Accepted:

        return None

    new_number = number_edit.text().strip()

    new_name = name_edit.text().strip()

    new_country = country_edit.currentText().strip()

    new_url = url_edit.text().strip()

    selected_logo = logo_edit.text().strip()

    if not new_number:

        QMessageBox.warning(
            dialog,
            "Manage Channel",
            "Please enter a channel number."
        )

        return None

    if not new_number.isdigit():

        QMessageBox.warning(
            dialog,
            "Manage Channel",
            "Channel number must contain only numbers."
        )

        return None

    if not new_name:

        QMessageBox.warning(
            dialog,
            "Manage Channel",
            "Please enter a channel name."
        )

        return None

    if not new_url:

        QMessageBox.warning(
            dialog,
            "Manage Channel",
            "Please enter a stream URL."
        )

        return None

    new_number = str(
        int(new_number)
    )

    if (
        new_number != number
        and new_number in channels
    ):

        QMessageBox.warning(
            dialog,
            "Manage Channel",
            f"Channel {new_number} already exists."
        )

        return None

    saved_logo = selected_logo

    if (
        selected_logo
        and os.path.exists(
            selected_logo
        )
    ):

        try:

            logo_absolute = os.path.abspath(
                selected_logo
            )

            logos_absolute = os.path.abspath(
                CHANNEL_LOGOS_DIR
            )

            if not logo_absolute.startswith(
                logos_absolute
            ):

                extension = os.path.splitext(
                    selected_logo
                )[1]

                destination = os.path.join(
                    CHANNEL_LOGOS_DIR,
                    f"channel_{new_number}{extension}"
                )

                shutil.copy2(
                    selected_logo,
                    destination
                )

                saved_logo = destination

        except Exception as error:

            print(
                "Could not copy managed channel logo:"
            )

            print(
                error
            )

    updated_channel = {
        "name": new_name,
        "country": new_country,
        "url": new_url,
        "logo": saved_logo
    }

    if new_number != number:

        del channels[
            number
        ]

        channels[
            new_number
        ] = updated_channel

        for index in range(
            len(custom_channel_list)
        ):

            if custom_channel_list[index] == number:

                custom_channel_list[index] = new_number

    else:

        channels[
            number
        ] = updated_channel

    custom_channel_list.sort(
        key=lambda x: int(x)
    )

    save_channels()

    save_custom_channel_list()

    if (
        channel_number.text()
        == str(number).zfill(2)
    ):

        play_channel(
            new_number
        )

    QMessageBox.information(
        parent,
        "Manage Channel",
        "Channel updated successfully."
    )

    return new_number


def delete_channel(
    number,
    parent,
    refresh_callback
):

    number = str(
        number
    )

    if number not in channels:

        return

    channel = channels[
        number
    ]

    result = QMessageBox.question(
        parent,
        "Delete Channel",
        (
            f"Are you sure you want to delete "
            f"CH {number.zfill(2)} - "
            f"{channel.get('name', 'Unknown channel')}?"
        ),
        QMessageBox.Yes
        | QMessageBox.No,
        QMessageBox.No
    )

    if result != QMessageBox.Yes:

        return

    current_number = channel_number.text().strip()

    if current_number == str(number).zfill(2):

        if recording:

            stop_recording()

        if player is not None:

            try:

                player.stop()

            except Exception:

                pass

        info_bar.hide()

        record_button.hide()

        hide_channel_number_input()

        logo.clear()

        channel_name.clear()

        country.clear()

        channel_number.clear()

        video_surface.lower()

        video_placeholder.setText(
            "Select a channel!"
        )

        video_placeholder.show()

        video_placeholder.raise_()

    del channels[
        number
    ]

    if number in custom_channel_list:

        custom_channel_list.remove(
            number
        )

    custom_channel_list.sort(
        key=lambda x: int(x)
    )

    save_channels()

    save_custom_channel_list()

    if not channels:

        update_empty_state()

    refresh_callback()


def open_custom_channel_listing(
    parent
):

    dialog = QDialog(
        parent
    )

    dialog.setWindowTitle(
        "Custom Channel Listing"
    )

    dialog.setFixedSize(
        560,
        360
    )

    if os.path.exists(
        WINDOW_ICON_PATH
    ):

        dialog.setWindowIcon(
            QIcon(
                WINDOW_ICON_PATH
            )
        )

    main_layout = QVBoxLayout(
        dialog
    )

    main_layout.setContentsMargins(
        10,
        10,
        10,
        8
    )

    main_layout.setSpacing(
        6
    )

    title = QLabel(
        "Select and Manage your channels:"
    )

    main_layout.addWidget(
        title
    )

    list_widget = QListWidget()

    list_widget.setSelectionMode(
        QListWidget.SingleSelection
    )

    list_widget.setSpacing(
        0
    )

    list_widget.setUniformItemSizes(
        True
    )

    main_layout.addWidget(
        list_widget
    )

    def selected_number():

        item = (
            list_widget.currentItem()
        )

        if item is None:

            return None

        return str(
            item.data(
                Qt.UserRole
            )
        )

    def update_manage_button():

        manage_button.setEnabled(
            selected_number() is not None
        )

    def update_row_selection():

        current_item = (
            list_widget.currentItem()
        )

        for index in range(
            list_widget.count()
        ):

            item = list_widget.item(
                index
            )

            row_widget = (
                list_widget.itemWidget(
                    item
                )
            )

            if row_widget is None:

                continue

            if item == current_item:

                row_widget.setStyleSheet("""
                    QWidget {
                        background-color: #dbeeff;
                        border-bottom: 1px solid #9ac7ef;
                    }

                    QLabel {
                        background-color: transparent;
                        color: #111111;
                        border: none;
                    }
                """)

            else:

                row_widget.setStyleSheet("""
                    QWidget {
                        background-color: white;
                        border-bottom: 1px solid #d0d0d0;
                    }

                    QLabel {
                        background-color: transparent;
                        color: #111111;
                        border: none;
                    }
                """)

    def refresh_list(
        number_to_select=None
    ):

        list_widget.clear()

        ordered_numbers = sorted(
            custom_channel_list,
            key=lambda x: int(x)
        )

        for number in ordered_numbers:

            if number not in channels:

                continue

            channel = channels[
                number
            ]

            item = QListWidgetItem()

            item.setData(
                Qt.UserRole,
                number
            )

            item.setSizeHint(
                QSize(
                    0,
                    40
                )
            )

            row_widget = QWidget()

            row_layout = QHBoxLayout(
                row_widget
            )

            row_layout.setContentsMargins(
                8,
                5,
                8,
                5
            )

            row_layout.setSpacing(
                8
            )

            name_label = QLabel(
                (
                    f"CH {number.zfill(2)} - "
                    f"{channel.get('name', 'Unknown channel')}"
                )
            )

            row_layout.addWidget(
                name_label
            )

            row_layout.addStretch()

            delete_button = QPushButton(
                "Delete"
            )

            delete_button.setFixedSize(
                70,
                28
            )

            delete_button.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    color: #222222;
                    border: 1px solid #8a8a8a;
                    border-radius: 14px;
                    padding: 2px 10px;
                    min-height: 0px;
                }

                QPushButton:hover {
                    background-color: #ffffff;
                    border: 1px solid #6f6f6f;
                }

                QPushButton:pressed {
                    background-color: #dddddd;
                    border: 1px solid #666666;
                }
            """)

            def handle_delete(
                checked=False,
                channel_number_value=number
            ):

                delete_channel(
                    channel_number_value,
                    dialog,
                    lambda:
                    refresh_list()
                )

                update_row_selection()

                update_manage_button()

            delete_button.clicked.connect(
                handle_delete
            )

            row_layout.addWidget(
                delete_button
            )

            def select_row(
                event,
                target_item=item
            ):

                list_widget.setCurrentItem(
                    target_item
                )

                update_row_selection()

                update_manage_button()

            row_widget.mousePressEvent = select_row

            name_label.mousePressEvent = (
                lambda event,
                target_item=item:
                (
                    list_widget.setCurrentItem(
                        target_item
                    ),
                    update_row_selection(),
                    update_manage_button()
                )
            )

            list_widget.addItem(
                item
            )

            list_widget.setItemWidget(
                item,
                row_widget
            )

        if number_to_select is not None:

            for index in range(
                list_widget.count()
            ):

                item = list_widget.item(
                    index
                )

                item_number = str(
                    item.data(
                        Qt.UserRole
                    )
                )

                if item_number == str(
                    number_to_select
                ):

                    list_widget.setCurrentItem(
                        item
                    )

                    break

        update_row_selection()

        update_manage_button()

    bottom_bar = QHBoxLayout()

    manage_button = QPushButton(
        "Manage"
    )

    manage_button.setEnabled(
        False
    )

    manage_button.setFixedHeight(
        28
    )

    manage_button.setStyleSheet("""
        QPushButton {
            background-color: #f5f5f5;
            color: #222222;
            border: 1px solid #8a8a8a;
            border-radius: 14px;
            padding: 2px 14px;
            min-height: 0px;
        }

        QPushButton:hover {
            background-color: #ffffff;
            border: 1px solid #6f6f6f;
        }

        QPushButton:pressed {
            background-color: #dddddd;
            border: 1px solid #666666;
        }

        QPushButton:disabled {
            background-color: #eeeeee;
            color: #888888;
            border: 1px solid #c0c0c0;
        }
    """)

    bottom_bar.addWidget(
        manage_button
    )

    bottom_bar.addStretch()

    save_button = QPushButton(
        "Save"
    )

    save_button.setFixedHeight(
        28
    )

    cancel_button = QPushButton(
        "Cancel"
    )

    cancel_button.setFixedHeight(
        28
    )

    bottom_bar.addWidget(
        save_button
    )

    bottom_bar.addWidget(
        cancel_button
    )

    main_layout.addLayout(
        bottom_bar
    )

    list_widget.currentItemChanged.connect(
        lambda current, previous:
        (
            update_row_selection(),
            update_manage_button()
        )
    )

    def handle_manage():

        number = selected_number()

        if number is None:

            return

        new_number = manage_channel(
            number,
            dialog
        )

        if new_number is None:

            return

        custom_channel_list.sort(
            key=lambda x: int(x)
        )

        save_custom_channel_list()

        refresh_list(
            new_number
        )

    manage_button.clicked.connect(
        handle_manage
    )

    def save_listing():

        global custom_channel_list

        new_list = []

        for index in range(
            list_widget.count()
        ):

            item = list_widget.item(
                index
            )

            number = str(
                item.data(
                    Qt.UserRole
                )
            )

            if (
                number in channels
                and number not in new_list
            ):

                new_list.append(
                    number
                )

        new_list.sort(
            key=lambda x: int(x)
        )

        custom_channel_list = new_list

        save_custom_channel_list()

        dialog.accept()

    save_button.clicked.connect(
        save_listing
    )

    cancel_button.clicked.connect(
        dialog.reject
    )

    refresh_list()

    dialog.exec()


def open_help():

    dialog = QDialog(
        window
    )

    dialog.setWindowTitle(
        "Zap - Help"
    )

    dialog.setFixedSize(
        560,
        430
    )

    if os.path.exists(
        WINDOW_ICON_PATH
    ):

        dialog.setWindowIcon(
            QIcon(
                WINDOW_ICON_PATH
            )
        )

    main_layout = QVBoxLayout(
        dialog
    )

    main_layout.setContentsMargins(
        15,
        15,
        15,
        12
    )

    main_layout.setSpacing(
        10
    )

    what_title = QLabel(
        "What happens if...?"
    )

    what_title.setStyleSheet(
        "font-weight: bold; font-size: 10pt;"
    )

    main_layout.addWidget(
        what_title
    )

    what_text = QLabel(
        """
<b>What happens if I enter a channel number?</b><br>
The number of channel redirects you to that channel. It will show a number on screen in case you're wrong.

<br><br>

<b>What happens if the channel does not load?</b><br>
The stream may be unavailable. You will need to change the <b>Stream URL</b> or wait.
"""
    )

    what_text.setWordWrap(
        True
    )

    what_text.setTextFormat(
        Qt.RichText
    )

    main_layout.addWidget(
        what_text
    )

    how_title = QLabel(
        "How do I...?"
    )

    how_title.setStyleSheet(
        "font-weight: bold; font-size: 10pt;"
    )

    main_layout.addWidget(
        how_title
    )

    how_text = QLabel(
        """
<b>How do I change channels?</b><br>
Type the channel number and press Enter.

<br><br>

<b>How do I start and end a recording?</b><br>
Press the <b>Record button</b> to start recording, press again to stop it. Make sure to be on a channel.

<br><br>

<b>How do I add a channel?</b><br>
Open <b>Add Channel...</b> from the top menu.

<br><br>

<b>How do I edit a channel?</b><br>
Open <b>Options</b>, select <b>Custom Channel Listing</b>, select the channel and press <b>Manage</b>.

<br><br>

<b>How do I remove a channel?</b><br>
Open <b>Options</b>, select <b>Custom Channel Listing</b>, then select the channel and press <b>Delete</b>.
"""
    )

    how_text.setWordWrap(
        True
    )

    how_text.setTextFormat(
        Qt.RichText
    )

    main_layout.addWidget(
        how_text
    )

    keyboard_title = QLabel(
        "Keyboard"
    )

    keyboard_title.setStyleSheet(
        "font-weight: bold; font-size: 10pt;"
    )

    main_layout.addWidget(
        keyboard_title
    )

    keyboard_text = QLabel(
        """
<b>0 - 9</b> &nbsp;&nbsp; Enter a channel number<br>
<b>Enter</b> &nbsp;&nbsp; Go to the inputted channel<br>
<b>←</b> &nbsp;&nbsp; Previous channel<br>
<b>→</b> &nbsp;&nbsp; Next channel
"""
    )

    keyboard_text.setTextFormat(
        Qt.RichText
    )

    main_layout.addWidget(
        keyboard_text
    )

    main_layout.addStretch()

    close_button = QPushButton(
        "Close"
    )

    close_button.clicked.connect(
        dialog.accept
    )

    main_layout.addWidget(
        close_button,
        alignment=Qt.AlignRight
    )

    dialog.exec()


def open_options():

    dialog = QDialog(
        window
    )

    dialog.setWindowTitle(
        "Options"
    )

    dialog.setFixedSize(
        390,
        150
    )

    if os.path.exists(
        WINDOW_ICON_PATH
    ):

        dialog.setWindowIcon(
            QIcon(
                WINDOW_ICON_PATH
            )
        )

    options_layout = QVBoxLayout(
        dialog
    )

    options_layout.setContentsMargins(
        15,
        15,
        15,
        15
    )

    custom_button = QPushButton(
        "Custom Channel Listing"
    )

    custom_button.setFixedHeight(
        32
    )

    options_layout.addWidget(
        custom_button
    )

    options_layout.addStretch()

    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok
        | QDialogButtonBox.Cancel
    )

    options_layout.addWidget(
        buttons
    )

    custom_button.clicked.connect(
        lambda:
        open_custom_channel_listing(
            dialog
        )
    )

    buttons.accepted.connect(
        dialog.accept
    )

    buttons.rejected.connect(
        dialog.reject
    )

    dialog.exec()


def add_channel():

    dialog = QDialog(
        window
    )

    dialog.setWindowTitle(
        "Add Channel..."
    )

    dialog.setFixedSize(
        460,
        250
    )

    if os.path.exists(
        WINDOW_ICON_PATH
    ):

        dialog.setWindowIcon(
            QIcon(
                WINDOW_ICON_PATH
            )
        )

    form = QFormLayout(
        dialog
    )

    form.setContentsMargins(
        15,
        15,
        15,
        15
    )

    form.setSpacing(
        10
    )

    number_edit = QLineEdit()

    number_edit.setPlaceholderText(
        "Example: 10"
    )

    name_edit = QLineEdit()

    name_edit.setPlaceholderText(
        "Example: Canal 10"
    )

    country_edit = QComboBox()

    country_edit.addItems(
        COUNTRIES
    )

    country_edit.setCurrentText(
        "Uruguay"
    )

    country_edit.setMaxVisibleItems(
        12
    )

    url_edit = QLineEdit()

    url_edit.setPlaceholderText(
        "https://..."
    )

    logo_edit = QLineEdit()

    logo_edit.setPlaceholderText(
        "Optional"
    )

    logo_edit.setReadOnly(
        True
    )

    browse_button = QPushButton(
        "Browse..."
    )

    logo_widget = QWidget()

    logo_layout = QHBoxLayout(
        logo_widget
    )

    logo_layout.setContentsMargins(
        0,
        0,
        0,
        0
    )

    logo_layout.addWidget(
        logo_edit
    )

    logo_layout.addWidget(
        browse_button
    )

    def browse_logo():

        file_path, _ = QFileDialog.getOpenFileName(
            dialog,
            "Select channel logo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )

        if file_path:

            logo_edit.setText(
                file_path
            )

    browse_button.clicked.connect(
        browse_logo
    )

    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok
        | QDialogButtonBox.Cancel
    )

    form.addRow(
        "Channel number:",
        number_edit
    )

    form.addRow(
        "Channel name:",
        name_edit
    )

    form.addRow(
        "Country:",
        country_edit
    )

    form.addRow(
        "Stream URL:",
        url_edit
    )

    form.addRow(
        "Logo:",
        logo_widget
    )

    form.addRow(
        buttons
    )

    buttons.accepted.connect(
        dialog.accept
    )

    buttons.rejected.connect(
        dialog.reject
    )

    if dialog.exec() != QDialog.Accepted:

        return

    number = number_edit.text().strip()

    name = name_edit.text().strip()

    country_value = country_edit.currentText().strip()

    url = url_edit.text().strip()

    selected_logo = logo_edit.text().strip()

    if not number:

        QMessageBox.warning(
            window,
            "Add Channel",
            "Please enter a channel number."
        )

        return

    if not number.isdigit():

        QMessageBox.warning(
            window,
            "Add Channel",
            "Channel number must contain only numbers."
        )

        return

    if not name:

        QMessageBox.warning(
            window,
            "Add Channel",
            "Please enter a channel name."
        )

        return

    if not url:

        QMessageBox.warning(
            window,
            "Add Channel",
            "Please enter a stream URL."
        )

        return

    number = str(
        int(number)
    )

    if number in channels:

        QMessageBox.warning(
            window,
            "Add Channel",
            f"Channel {number} already exists."
        )

        return

    saved_logo = ""

    if (
        selected_logo
        and os.path.exists(
            selected_logo
        )
    ):

        extension = os.path.splitext(
            selected_logo
        )[1]

        destination = os.path.join(
            CHANNEL_LOGOS_DIR,
            f"channel_{number}{extension}"
        )

        try:

            shutil.copy2(
                selected_logo,
                destination
            )

            saved_logo = destination

        except Exception as error:

            print(
                "Could not copy channel logo:"
            )

            print(
                error
            )

    channels[number] = {
        "name": name,
        "country": country_value,
        "url": url,
        "logo": saved_logo
    }

    if number not in custom_channel_list:

        custom_channel_list.append(
            number
        )

    custom_channel_list.sort(
        key=lambda x: int(x)
    )

    save_channels()

    save_custom_channel_list()

    if len(channels) == 1:

        video_surface.lower()

        video_placeholder.setText(
            "Select a channel!"
        )

        video_placeholder.show()

        video_placeholder.raise_()

    QMessageBox.information(
        window,
        "Add Channel",
        f"Channel {number} added successfully."
    )


options_action.triggered.connect(
    open_options
)

help_action.triggered.connect(
    open_help
)

add_channel_action.triggered.connect(
    add_channel
)


window.channel_buffer = ""


def switch_channel(
    direction
):

    if not custom_channel_list:

        return

    ordered_channels = sorted(
        custom_channel_list,
        key=lambda x: int(x)
    )

    current_number = (
        channel_number.text()
        .strip()
    )

    try:

        current_number = str(
            int(current_number)
        )

    except ValueError:

        return

    if current_number not in ordered_channels:

        return

    current_index = ordered_channels.index(
        current_number
    )

    new_index = (
        current_index + direction
    ) % len(
        ordered_channels
    )

    new_number = ordered_channels[
        new_index
    ]

    play_channel(
        new_number
    )

    window.channel_buffer = ""

    hide_channel_number_input()


def keyPressEvent(event):

    if event.key() in (
        Qt.Key_Return,
        Qt.Key_Enter
    ):

        if window.channel_buffer:

            number = window.channel_buffer

            window.channel_buffer = ""

            hide_channel_number_input()

            play_channel(
                number
            )

        return

    if (
        Qt.Key_0
        <= event.key()
        <= Qt.Key_9
    ):

        digit = str(
            event.key()
            - Qt.Key_0
        )

        window.channel_buffer += digit

        print(
            "Channel input:",
            window.channel_buffer
        )

        show_channel_number_input()

        return

    if event.key() == Qt.Key_Left:

        switch_channel(
            -1
        )

        return

    if event.key() == Qt.Key_Right:

        switch_channel(
            1
        )

        return

    QMainWindow.keyPressEvent(
        window,
        event
    )


window.keyPressEvent = keyPressEvent


class ChannelKeyFilter(QObject):

    def eventFilter(
        self,
        obj,
        event
    ):

        if event.type() != QEvent.KeyPress:

            return False

        active_modal = (
            QApplication.activeModalWidget()
        )

        if active_modal is not None:

            return False

        if event.key() == Qt.Key_Left:

            switch_channel(
                -1
            )

            return True

        if event.key() == Qt.Key_Right:

            switch_channel(
                1
            )

            return True

        return False


channel_key_filter = ChannelKeyFilter()

app.installEventFilter(
    channel_key_filter
)


old_resize_event = window.resizeEvent


def resize_event(event):

    resize_video_surface()

    resize_channel_number_overlay()

    old_resize_event(
        event
    )


window.resizeEvent = resize_event


def close_vlc():

    global recording
    global record_player
    global record_instance

    recording = False

    if record_player is not None:

        try:

            record_player.stop()

        except Exception:

            pass

        try:

            record_player.release()

        except Exception:

            pass

        record_player = None

    if record_instance is not None:

        try:

            record_instance.release()

        except Exception:

            pass

        record_instance = None

    if player is not None:

        try:

            player.stop()

        except Exception:

            pass

        try:

            player.release()

        except Exception:

            pass

    try:

        if vlc_instance is not None:

            vlc_instance.release()

    except Exception:

        pass


window.destroyed.connect(
    close_vlc
)


hide_channel_number_input()

update_record_button_style()

resize_video_surface()

resize_channel_number_overlay()

if not channels:

    update_empty_state()


window.show()

resize_video_surface()

resize_channel_number_overlay()

if info_bar.isVisible():

    record_button.show()
    record_button.raise_()


sys.exit(
    app.exec()
)