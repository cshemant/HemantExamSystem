"""V186 opt-in AI / computer-vision helpers.

Does not identify people, store raw frames, or determine misconduct. Face
presence is fallible; anomalous response patterns require human review.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import os
import threading


@lru_cache(maxsize=2)
def ai_proctor_dependencies(include_phone=False):
    """Lightweight package checks for exam startup; model loading is admin-only.

    Only the AI settings page/save verifies the ONNX model. Ordinary webcam
    preflight never loads a Deep Learning model or imports scikit-learn.
    """
    from importlib.util import find_spec
    cv=find_spec('cv2') is not None and find_spec('numpy') is not None
    ml=find_spec('sklearn') is not None
    phone=phone_detector_ready() if include_phone and cv else False
    return {'cv':cv,'ml':ml,'phone':phone}


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
    if not isinstance(jpeg, bytes) or len(jpeg) < 100 or len(jpeg) > 120000 or not jpeg.startswith(b'\xff\xd8'):
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


# COCO-80 object detector, class 67 = cell phone. This is Deep Learning inference
# using OpenCV DNN and a separately provided YOLOv8n ONNX model. The model must
# be operator-installed and licensed; no weights are downloaded in exam traffic.
_PHONE_DNN_LOCK = threading.Lock()
_PHONE_CLASS_COCO80 = 67

def phone_model_path():
    fallback = Path(__file__).resolve().parent / 'models' / 'phone_detector.onnx'
    return Path(os.getenv('EXAM_PHONE_MODEL_PATH') or fallback).expanduser().resolve()

@lru_cache(maxsize=1)
def _phone_net():
    path = phone_model_path()
    if not path.is_file() or path.stat().st_size < 1_000_000:
        raise RuntimeError('A COCO-80 YOLOv8 ONNX phone model is not configured')
    try:
        import cv2
        return cv2.dnn.readNetFromONNX(str(path))
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('OpenCV DNN is unavailable') from exc
    except Exception as exc:
        raise RuntimeError('The phone ONNX model cannot be loaded') from exc

def phone_detector_ready():
    # Lightweight capability check for the student start page and admin form.
    # Loading a 12+ MB ONNX network here stalls webcam permission / exam start;
    # validation and actual inference occur only on periodic samples.
    from importlib.util import find_spec
    path=phone_model_path()
    return bool(find_spec('cv2') and path.is_file() and path.stat().st_size >= 1_000_000)

# COCO classes supported by the supplied 80-class ONNX model. Tablets may
# appear as either class, but many devices are outside this model's vocabulary.
_SUPPORTED_DEVICE_CLASSES = {67: 'mobile phone', 63: 'laptop or tablet'}


def detect_device_in_jpeg(jpeg):
    """Return a possible visible device's label/confidence, 0 when absent,
    or None when another worker is already processing a frame.

    Accepts YOLOv8 COCO80 raw ONNX outputs [1,84,N]/[1,N,84]. Apply
    class-specific confidence and NMS rather than requiring class 67 to be
    each proposal's top class. A single model score is not proof of misconduct.
    """
    if not isinstance(jpeg, bytes) or not 100 <= len(jpeg) <= 120000 or not jpeg.startswith(b'\xff\xd8'):
        raise ValueError('Invalid device-analysis JPEG')
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('OpenCV, Pillow and NumPy required') from exc
    with Image.open(BytesIO(jpeg)) as image:
        w,h=image.size
        if image.format!='JPEG' or min(w,h)<64 or max(w,h)>640 or w*h>307200:
            raise ValueError('Unsupported camera frame dimensions')
    frame=cv2.imdecode(np.frombuffer(jpeg,dtype=np.uint8),cv2.IMREAD_COLOR)
    if frame is None:raise ValueError('JPEG decode failed')
    h,w=frame.shape[:2];scale=min(640/w,640/h)
    nw,nh=max(1,round(w*scale)),max(1,round(h*scale))
    padded=np.full((640,640,3),114,dtype=np.uint8)
    x,y=(640-nw)//2,(640-nh)//2
    padded[y:y+nh,x:x+nw]=cv2.resize(frame,(nw,nh),interpolation=cv2.INTER_LINEAR)
    blob=cv2.dnn.blobFromImage(padded,scalefactor=1/255.0,size=(640,640),swapRB=True,crop=False)
    if not _PHONE_DNN_LOCK.acquire(blocking=False):return None
    try:
        net=_phone_net()
        net.setInput(blob)
        output=np.asarray(net.forward())
    except RuntimeError:raise
    except Exception as exc:raise RuntimeError('Device detector inference failed') from exc
    finally:_PHONE_DNN_LOCK.release()
    if output.ndim!=3 or output.shape[0]!=1:
        raise RuntimeError('Unsupported ONNX output, expected YOLOv8 COCO-80')
    if output.shape[1]==84:rows=output[0].T
    elif output.shape[2]==84:rows=output[0]
    else:raise RuntimeError('Expected 84 YOLOv8 COCO-80 output channels')
    if len(rows)==0:return {'label':'none','confidence':0.0}
    if not np.isfinite(rows).all():raise RuntimeError('Nonfinite ONNX prediction')
    best_label='none';best_score=0.0
    # Only class scores corresponding to supported devices. NMS filters
    # duplicate overlapping predictions; candidate boxes are normalized
    # model coordinates in the 640-pixel letterbox.
    for class_id,label in _SUPPORTED_DEVICE_CLASSES.items():
        scores=rows[:,4+class_id]
        mask=scores>=0.15
        if not mask.any():continue
        candidates=rows[mask,:4]
        candidate_scores=scores[mask].astype(float)
        boxes=[]
        for cx,cy,bw,bh in candidates:
            boxes.append([float(cx-bw/2),float(cy-bh/2),float(bw),float(bh)])
        retained=cv2.dnn.NMSBoxes(boxes,candidate_scores.tolist(),0.15,0.45)
        if retained is None or len(retained)==0:continue
        highest=max(float(candidate_scores[int(i)]) for i in np.asarray(retained).reshape(-1))
        if highest>best_score:best_label=label;best_score=highest
    return {'label':best_label,'confidence':min(1.0,best_score)}


def detect_phone_in_jpeg(jpeg):
    """Backward-compatible confidence-only interface used by old modules."""
    result=detect_device_in_jpeg(jpeg)
    return float(result['confidence']) if result is not None else None
