"""Pure, testable V185 exam-integrity helpers. No browser/client JS is trusted."""
import hashlib
import hmac
import re


def validate_seb_config_hash(url: str, config_key: str, received: str) -> bool:
    """Validate SEB ConfigKeyHash = SHA256(absolute URL without fragment + config key).

    The Config Key is the hexadecimal SHA256 value shown by SEB after the
    final configuration is saved. URL must be built from a trusted origin.
    """
    if not isinstance(config_key,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',config_key):return False
    if not isinstance(received,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',received):return False
    clean_url=url.split('#',1)[0]
    expected=hashlib.sha256((clean_url+config_key.lower()).encode('utf-8')).hexdigest()
    return hmac.compare_digest(expected,received.lower())


def security_event_weight(event_type:str)->int:
    """Only focus loss can count toward legacy automatic integrity termination.

    Copy/paste/context-menu may arise from accessibility tools and do not
    establish misconduct; log them without triggering automatic penalties.
    """
    return int(event_type in {'tab_hidden','fullscreen_exit'})


def visibility_allowed_question(question_id:int, current_id:int|None, sequential:bool)->bool:
    return bool(not sequential or question_id==current_id)
