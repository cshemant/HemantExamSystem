"""V186 opt-in AI / computer-vision helpers.

Does not identify people, store raw frames, or determine misconduct. Face
presence is fallible; anomalous response patterns require human review.
"""
from functools import lru_cache
from io import BytesIO


@lru_cache(maxsize=1)
def ai_proctor_dependencies():
    """Check installed packages without importing the heavy ML model on exam start.

    Full model and OpenCV imports occur only when their actual operations run.
    A package check is advisory; frame processing still fails closed if CV is broken.
    """
    from importlib.util import find_spec
    return {'cv': find_spec('cv2') is not None and find_spec('numpy') is not None,
            'ml': find_spec('sklearn') is not None}


@lru_cache(maxsize=1)
def _face_cascade():
    try:
        import cv2
        path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            raise RuntimeError('OpenCV frontal-face cascade unavailable')
        return cascade
    except ImportError as exc:
        raise RuntimeError('OpenCV is not installed') from exc


def count_faces_in_jpeg(jpeg: bytes) -> int:
    """Return estimated face count from one small JPEG. No identity matching.

    A face detection miss is inconclusive, not evidence of cheating.
    """
    if not isinstance(jpeg, bytes) or len(jpeg) < 100 or len(jpeg) > 80000 or not jpeg.startswith(b'\xff\xd8'):
        raise ValueError('Invalid or oversized JPEG')
    # Inspect compressed image dimensions before decompressing an untrusted JPEG.
    try:
        from PIL import Image
        with Image.open(BytesIO(jpeg)) as header:
            width, height = header.size
            if min(width, height) < 64 or max(width, height) > 640 or width*height > 307200:
                raise ValueError('Unsupported frame dimensions')
            if header.format != 'JPEG':
                raise ValueError('Expected JPEG')
    except (OSError, SyntaxError) as exc:
        raise ValueError('Invalid JPEG structure') from exc
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError('CV dependencies missing') from exc
    img = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None or img.ndim != 2:
        raise ValueError('Unreadable JPEG')
    h, w = img.shape
    if min(h, w) < 64 or max(h, w) > 640 or w*h > 307200:
        raise ValueError('Unsupported frame dimensions')
    img = cv2.equalizeHist(img)
    return int(len(_face_cascade().detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(28, 28))))


def score_exam_outliers(vectors, minimum_samples=25):
    """Run a genuine unsupervised anomaly model on completed attempts.

    A prediction of 'Review' only means unusually different from this exam's
    peer history, not a probability of cheating. Below the sample threshold,
    no model is trained and no risk is asserted.
    """
    if not vectors:
        return []
    if len(vectors) < minimum_samples:
        return ['Insufficient data'] * len(vectors)
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return ['Dependency missing'] * len(vectors)
    array = np.asarray(vectors, dtype=np.float64)
    if array.ndim != 2 or not np.isfinite(array).all() or array.shape[1] != 6:
        raise ValueError('Invalid anomaly features')
    if not np.any(np.std(array, axis=0) > 1e-9):
        return ['No variation'] * len(vectors)
    # Contamination sets a baseline tail fraction, not a misconduct rate.
    model = IsolationForest(n_estimators=100, contamination=0.08, random_state=42, n_jobs=1)
    labels = model.fit_predict(array)
    return ['Review' if label == -1 else 'Typical' for label in labels]
