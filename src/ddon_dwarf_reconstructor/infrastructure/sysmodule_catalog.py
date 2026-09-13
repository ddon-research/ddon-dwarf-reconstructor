"""Static Sysmodule IDs reviewed from the local SDK HTML reference."""

from __future__ import annotations

from ..domain.models.sysmodule import SysmoduleId

SYSMODULE_SOURCE = r"D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Generating_and_Using_Dynamic_Libraries\Sysmodule-Reference\ps4-module-ids.html"
SYSMODULE_SDK_VERSION = "12.00"

_VALUES = (
    ("SCE_SYSMODULE_FIBER", 6),
    ("SCE_SYSMODULE_ULT", 7),
    ("SCE_SYSMODULE_NGS2", 11),
    ("SCE_SYSMODULE_XML", 23),
    ("SCE_SYSMODULE_NP_UTILITY", 25),
    ("SCE_SYSMODULE_VOICE", 26),
    ("SCE_SYSMODULE_VOICEQOS", 27),
    ("SCE_SYSMODULE_NP_MATCHING2", 28),
    ("SCE_SYSMODULE_NP_SCORE_RANKING", 30),
    ("SCE_SYSMODULE_RUDP", 33),
    ("SCE_SYSMODULE_NP_TUS", 44),
    ("SCE_SYSMODULE_FACE", 56),
    ("SCE_SYSMODULE_GAME_LIVE_STREAMING", 129),
    ("SCE_SYSMODULE_PLAYGO", 131),
    ("SCE_SYSMODULE_FONT", 132),
    ("SCE_SYSMODULE_VIDEO_RECORDING", 133),
    ("SCE_SYSMODULE_S3DCONVERSION", 134),
    ("SCE_SYSMODULE_AUDIODEC", 136),
    ("SCE_SYSMODULE_JPEG_DEC", 138),
    ("SCE_SYSMODULE_JPEG_ENC", 139),
    ("SCE_SYSMODULE_PNG_DEC", 140),
    ("SCE_SYSMODULE_PNG_ENC", 141),
    ("SCE_SYSMODULE_MOVE", 143),
    ("SCE_SYSMODULE_PAD_TRACKER", 145),
    ("SCE_SYSMODULE_DEPTH", 146),
    ("SCE_SYSMODULE_HAND", 147),
    ("SCE_SYSMODULE_LIBIME", 149),
    ("SCE_SYSMODULE_IME_DIALOG", 150),
    ("SCE_SYSMODULE_NP_PARTY", 151),
    ("SCE_SYSMODULE_FONT_FT", 152),
    ("SCE_SYSMODULE_FREETYPE_OT", 153),
    ("SCE_SYSMODULE_FREETYPE_OL", 154),
    ("SCE_SYSMODULE_FREETYPE_OPT_OL", 155),
    ("SCE_SYSMODULE_SCREEN_SHOT", 156),
    ("SCE_SYSMODULE_NP_AUTH", 157),
    ("SCE_SYSMODULE_SULPHA", 159),
    ("SCE_SYSMODULE_SAVE_DATA_DIALOG", 160),
    ("SCE_SYSMODULE_INVITATION_DIALOG", 162),
    ("SCE_SYSMODULE_DEBUG_KEYBOARD", 163),
    ("SCE_SYSMODULE_MESSAGE_DIALOG", 164),
    ("SCE_SYSMODULE_AV_PLAYER", 165),
    ("SCE_SYSMODULE_CONTENT_EXPORT", 166),
    ("SCE_SYSMODULE_AUDIO_3D", 167),
    ("SCE_SYSMODULE_NP_COMMERCE", 168),
    ("SCE_SYSMODULE_MOUSE", 169),
    ("SCE_SYSMODULE_WEB_BROWSER_DIALOG", 171),
    ("SCE_SYSMODULE_ERROR_DIALOG", 172),
    ("SCE_SYSMODULE_NP_TROPHY", 173),
    ("SCE_SYSMODULE_MOVE_TRACKER", 177),
    ("SCE_SYSMODULE_NP_PROFILE_DIALOG", 178),
    ("SCE_SYSMODULE_NP_FRIEND_LIST_DIALOG", 179),
    ("SCE_SYSMODULE_APP_CONTENT", 180),
    ("SCE_SYSMODULE_NP_SIGNALING", 181),
    ("SCE_SYSMODULE_REMOTE_PLAY", 182),
    ("SCE_SYSMODULE_USBD", 183),
    ("SCE_SYSMODULE_RANDOM", 186),
    ("SCE_SYSMODULE_M4AAC_ENC", 188),
    ("SCE_SYSMODULE_AUDIODEC_CPU", 189),
    ("SCE_SYSMODULE_ZLIB", 197),
    ("SCE_SYSMODULE_CONTENT_SEARCH", 199),
    ("SCE_SYSMODULE_SHARE_UTILITY", 200),
    ("SCE_SYSMODULE_DECI4H", 202),
    ("SCE_SYSMODULE_HEAD_TRACKER", 203),
    ("SCE_SYSMODULE_SYSTEM_GESTURE", 206),
    ("SCE_SYSMODULE_VIDEODEC2", 207),
    ("SCE_SYSMODULE_AT9_ENC", 209),
    ("SCE_SYSMODULE_CONVERT_KEYCODE", 210),
    ("SCE_SYSMODULE_SHARE_PLAY", 211),
    ("SCE_SYSMODULE_HMD", 212),
    ("SCE_SYSMODULE_FACE_TRACKER", 216),
    ("SCE_SYSMODULE_HAND_TRACKER", 217),
    ("SCE_SYSMODULE_AUDIODEC_CPU_HEVAG", 225),
    ("SCE_SYSMODULE_LOGIN_DIALOG", 226),
    ("SCE_SYSMODULE_LOGIN_SERVICE", 227),
    ("SCE_SYSMODULE_SIGNIN_DIALOG", 228),
    ("SCE_SYSMODULE_VDECSW", 229),
    ("SCE_SYSMODULE_JSON2", 231),
    ("SCE_SYSMODULE_AUDIO_LATENCY_ESTIMATION", 232),
    ("SCE_SYSMODULE_HMD_SETUP_DIALOG", 235),
    ("SCE_SYSMODULE_VR_TRACKER", 237),
    ("SCE_SYSMODULE_CONTENT_DELETE", 238),
    ("SCE_SYSMODULE_IME_BACKEND", 239),
    ("SCE_SYSMODULE_NET_CTL_AP_DIALOG", 240),
    ("SCE_SYSMODULE_PLAYGO_DIALOG", 241),
    ("SCE_SYSMODULE_SOCIAL_SCREEN", 242),
    ("SCE_SYSMODULE_VR_SERVICE_DIALOG", 253),
    ("SCE_SYSMODULE_JOB_MANAGER", 254),
    ("SCE_SYSMODULE_SOCIAL_SCREEN_DIALOG", 256),
    ("SCE_SYSMODULE_NP_TOOLKIT2", 258),
    ("SCE_SYSMODULE_CES_CS", 268),
    ("SCE_SYSMODULE_FONT_GSM", 309),
)

SYSMODULE_IDS = {
    name: SysmoduleId(name, value, SYSMODULE_SOURCE, SYSMODULE_SDK_VERSION)
    for name, value in _VALUES
}


def get_sysmodule_id(name: str) -> SysmoduleId:
    """Return one documented loader identifier."""
    try:
        return SYSMODULE_IDS[name]
    except KeyError as error:
        raise ValueError(f"Unknown Sysmodule identifier: {name}") from error


def list_sysmodule_ids() -> tuple[SysmoduleId, ...]:
    """Return the catalog in stable numeric/name order."""
    return tuple(sorted(SYSMODULE_IDS.values(), key=lambda item: (item.value, item.name)))


def is_sysmodule_value(value: int) -> bool:
    """Return whether a value is documented as a Sysmodule loader constant."""
    return any(item.value == value for item in SYSMODULE_IDS.values())


__all__ = [
    "SYSMODULE_IDS",
    "SYSMODULE_SDK_VERSION",
    "SYSMODULE_SOURCE",
    "get_sysmodule_id",
    "is_sysmodule_value",
    "list_sysmodule_ids",
]
