"""Consolidates all the functionality for extracting data from charts into one function."""

# Built-in imports
from functools import reduce
import json
from operator import concat
from pathlib import Path
from PIL import Image
from typing import Any, Dict, List, Tuple

# Internal Imports
from ..extraction.blood_pressure_and_heart_rate import (
    extract_heart_rate_and_blood_pressure,
)
from ..extraction.checkboxes import extract_checkboxes
from ..extraction.extraction_utilities import (
    combine_dictionaries,
    detect_objects_using_tiling,
    label_studio_to_bboxes,
)
from ..extraction.inhaled_volatile import extract_inhaled_volatile
from ..extraction.intraoperative_digit_boxes import (
    extract_drug_codes,
    extract_ett_size,
    extract_surgical_timing,
)
from ..extraction.physiological_indicators import extract_physiological_indicators
from ..extraction.preoperative_postoperative_digit_boxes import (
    extract_preop_postop_digit_data,
)
from ..image_registration.homography import homography_transform
from ..label_clustering.cluster import Cluster
from ..label_clustering.clustering_methods import (
    cluster_kmeans,
    cluster_boxes,
    find_legend_locations,
)
from ..label_clustering.isolate_labels import (
    isolate_blood_pressure_legend_bounding_boxes,
)
from ..object_detection_models.onnx_yolov11_detection import OnnxYolov11Detection
from ..object_detection_models.onnx_yolov11_pose_single import OnnxYolov11PoseSingle
from ..point_registration.homography import (
    find_homography,
    transform_box,
    transform_keypoint,
)
from ..utilities.annotations import BoundingBox
from ..utilities.detections import Detection

# External Imports
import numpy as np


PATH_TO_DATA: Path = (Path(__file__) / ".." / ".." / "data").resolve()
PATH_TO_MODELS: Path = PATH_TO_DATA / "models"
PATH_TO_MODEL_METADATA = PATH_TO_DATA / "model_metadata"
MODEL_CONFIG: Dict = json.loads(open(str(PATH_TO_DATA / "config.json"), "r").read())
INTRAOP_DOC_MODEL = OnnxYolov11Detection(
    PATH_TO_MODELS / MODEL_CONFIG["intraoperative_document_landmarks"]["name"],
    PATH_TO_MODEL_METADATA
    / MODEL_CONFIG["intraoperative_document_landmarks"]["name"].replace(
        ".onnx", ".json"
    ),
    MODEL_CONFIG["intraoperative_document_landmarks"]["imgsz"],
    MODEL_CONFIG["intraoperative_document_landmarks"]["imgsz"],
    lazy_loading=True,
)
PREOP_POSTOP_DOC_MODEL = OnnxYolov11Detection(
    PATH_TO_MODELS / MODEL_CONFIG["preop_postop_document_landmarks"]["name"],
    PATH_TO_MODEL_METADATA
    / MODEL_CONFIG["preop_postop_document_landmarks"]["name"].replace(".onnx", ".json"),
    MODEL_CONFIG["preop_postop_document_landmarks"]["imgsz"],
    MODEL_CONFIG["preop_postop_document_landmarks"]["imgsz"],
    lazy_loading=True,
)
NUMBERS_MODEL = OnnxYolov11Detection(
    PATH_TO_MODELS / MODEL_CONFIG["numbers"]["name"],
    PATH_TO_MODEL_METADATA / MODEL_CONFIG["numbers"]["name"].replace(".onnx", ".json"),
    MODEL_CONFIG["numbers"]["imgsz"],
    MODEL_CONFIG["numbers"]["imgsz"],
    lazy_loading=True,
)
SYSTOLIC_MODEL = OnnxYolov11PoseSingle(
    PATH_TO_MODELS / MODEL_CONFIG["systolic"]["name"],
    PATH_TO_MODEL_METADATA / MODEL_CONFIG["systolic"]["name"].replace(".onnx", ".json"),
    MODEL_CONFIG["systolic"]["imgsz"],
    MODEL_CONFIG["systolic"]["imgsz"],
    lazy_loading=True,
)
DIASTOLIC_MODEL = OnnxYolov11PoseSingle(
    PATH_TO_MODELS / MODEL_CONFIG["diastolic"]["name"],
    PATH_TO_MODEL_METADATA
    / MODEL_CONFIG["diastolic"]["name"].replace(".onnx", ".json"),
    MODEL_CONFIG["diastolic"]["imgsz"],
    MODEL_CONFIG["diastolic"]["imgsz"],
    lazy_loading=True,
)
HEART_RATE_MODEL = OnnxYolov11PoseSingle(
    PATH_TO_MODELS / MODEL_CONFIG["heart_rate"]["name"],
    PATH_TO_MODEL_METADATA
    / MODEL_CONFIG["heart_rate"]["name"].replace(".onnx", ".json"),
    MODEL_CONFIG["heart_rate"]["imgsz"],
    MODEL_CONFIG["heart_rate"]["imgsz"],
    lazy_loading=True,
)
CHECKBOXES_MODEL = OnnxYolov11Detection(
    PATH_TO_MODELS / MODEL_CONFIG["checkboxes"]["name"],
    PATH_TO_MODEL_METADATA
    / MODEL_CONFIG["checkboxes"]["name"].replace(".onnx", ".json"),
    MODEL_CONFIG["checkboxes"]["imgsz"],
    MODEL_CONFIG["checkboxes"]["imgsz"],
    lazy_loading=True
)


def digitize_sheet(intraop_image: Image.Image, preop_postop_image: Image.Image) -> Dict:
    """Digitizes a paper surgical record using smartphone images of the front and back.

    Args:
        `intraop_image` (Image.Image):
            A smartphone photograph of the intraoperative side of the paper
            anesthesia record.
        `preop_postop_image` (Image.Image):
            A smartphone photograph of the preoperative/postoperative side of the
            paper anesthesia record.

    Returns:
        A dictionary containing all the data from the anesthesia record.
    """
    data = dict()
    data.update(digitize_intraop_record(intraop_image))
    data.update(digitize_preop_postop_record(preop_postop_image))
    return data


def run_models(
    intraop_image: Image.Image, preop_postop_image: Image.Image
) -> Dict[str, List[Detection]]:
    """Runs all the models and puts their output into a dictionary.

    Args:
        `intraop_image` (Image.Image):
            A smartphone photograph of the intraoperative side of the paper
            anesthesia record.
        `preop_postop_image` (Image.Image):
            A smartphone photograph of the preoperative/postoperative side of the
            paper anesthesia record.

    Returns:
        A dictionary containing all the detections on both images. The structure of the dictionary
        is set up as:
        {
            "intraoperative": {
                "landmarks": [...],
                "numbers": [...],
                "checkboxes": [...],
                "systolic": [...],
                "diastoic": [...],
                "heart_rate": [...],
            },
            "preoperative_postoperative": {
                "landmarks": [...],
                "numbers": [...],
                "checkboxes": [...],
            }
        }
    """
    detections_dict: Dict[str, List[Detection]] = dict()
    detections_dict["intraoperative"] = run_intraoperative_models(intraop_image)
    detections_dict["preoperative_postoperative"] = (
        run_preoperative_postoperative_models(preop_postop_image)
    )
    return detections_dict


def run_intraoperative_models(intraop_image: Image.Image) -> Dict[str, List[Detection]]:
    """Runs all the models on the preoperative/postoperative image and outputs to a dictionary.

    Args:
        `intraop_image` (Image.Image):
            A smartphone photograph of the intraoperative side of the paper anesthesia record.

    Returns:
        A dictionary containing all of the detections on the intraoperative image.
        The structure of the dictionary is set up as:
        {
            "landmarks": [...],
            "numbers": [...],
            "checkboxes": [...],
            "systolic": [...],
            "diastoic": [...],
            "heart_rate": [...],
        }
    """
    detections_dict: Dict[str, List[Detection]] = dict()

    # landmarks
    landmark_tile_size: int = compute_tile_size(
        MODEL_CONFIG["intraoperative_document_landmarks"], intraop_image.size
    )
    detections_dict["landmarks"] = detect_objects_using_tiling(
        intraop_image,
        INTRAOP_DOC_MODEL,
        landmark_tile_size,
        landmark_tile_size,
        MODEL_CONFIG["intraoperative_document_landmarks"]["horz_overlap_proportion"],
        MODEL_CONFIG["intraoperative_document_landmarks"]["vert_overlap_proportion"],
    )

    # numbers
    digit_tile_size: int = compute_tile_size(
        MODEL_CONFIG["numbers"], intraop_image.size
    )
    detections_dict["numbers"] = detect_objects_using_tiling(
        intraop_image,
        NUMBERS_MODEL,
        digit_tile_size,
        digit_tile_size,
        MODEL_CONFIG["numbers"]["horz_overlap_proportion"],
        MODEL_CONFIG["numbers"]["vert_overlap_proportion"],
    )

    # checkboxes
    tile_size = compute_tile_size(MODEL_CONFIG["checkboxes"], intraop_image.size)
    detections_dict["checkboxes"] = detect_objects_using_tiling(
        intraop_image,
        CHECKBOXES_MODEL,
        tile_size,
        tile_size,
        MODEL_CONFIG["checkboxes"]["horz_overlap_proportion"],
        MODEL_CONFIG["checkboxes"]["vert_overlap_proportion"],
        nms_threshold=0.8,
    )

    # systolic
    sys_tile_size: int = compute_tile_size(MODEL_CONFIG["systolic"], intraop_image.size)
    detections_dict["systolic"] = detect_objects_using_tiling(
        intraop_image.copy(),
        SYSTOLIC_MODEL,
        sys_tile_size,
        sys_tile_size,
        MODEL_CONFIG["systolic"]["horz_overlap_proportion"],
        MODEL_CONFIG["systolic"]["vert_overlap_proportion"],
    )

    # diastolic
    dia_tile_size: int = compute_tile_size(
        MODEL_CONFIG["diastolic"], intraop_image.size
    )
    detections_dict["diastolic"] = detect_objects_using_tiling(
        intraop_image.copy(),
        DIASTOLIC_MODEL,
        dia_tile_size,
        dia_tile_size,
        MODEL_CONFIG["diastolic"]["horz_overlap_proportion"],
        MODEL_CONFIG["diastolic"]["vert_overlap_proportion"],
    )

    # heart rate
    hr_tile_size: int = compute_tile_size(
        MODEL_CONFIG["heart_rate"], intraop_image.size
    )
    detections_dict["heart_rate"] = detect_objects_using_tiling(
        intraop_image.copy(),
        HEART_RATE_MODEL,
        hr_tile_size,
        hr_tile_size,
        MODEL_CONFIG["heart_rate"]["horz_overlap_proportion"],
        MODEL_CONFIG["heart_rate"]["vert_overlap_proportion"],
    )

    return detections_dict


def run_preoperative_postoperative_models(
    preop_postop_image: Image.Image,
) -> Dict[str, List[Detection]]:
    """Runs all the models on the preoperative/postoperative image and outputs to a dictionary.

    Args:
        `preop_postop_image` (Image.Image):
            A smartphone photograph of the preoperative/postoperative side of the
            paper anesthesia record.

    Returns:
        A dictionary containing all of the detections on the preoperative/postoperative image.
        The structure of the dictionary is set up as:
        {
            "landmarks": [...],
            "numbers": [...],
            "checkboxes": [...],
        }
    """
    detections_dict: Dict[str, List[Detection]] = dict()

    # landmarks
    landmark_tile_size: int = compute_tile_size(
        MODEL_CONFIG["preop_postop_document_landmarks"],
        preop_postop_image.size,
    )
    detections_dict["landmarks"] = detect_objects_using_tiling(
        preop_postop_image,
        PREOP_POSTOP_DOC_MODEL,
        landmark_tile_size,
        landmark_tile_size,
        MODEL_CONFIG["preop_postop_document_landmarks"]["horz_overlap_proportion"],
        MODEL_CONFIG["preop_postop_document_landmarks"]["vert_overlap_proportion"],
    )

    # numbers
    digit_tile_size: int = compute_tile_size(
        MODEL_CONFIG["numbers"], preop_postop_image.size
    )
    detections_dict["numbers"] = detect_objects_using_tiling(
        preop_postop_image,
        NUMBERS_MODEL,
        digit_tile_size,
        digit_tile_size,
        MODEL_CONFIG["numbers"]["horz_overlap_proportion"],
        MODEL_CONFIG["numbers"]["vert_overlap_proportion"],
    )

    # checkboxes
    tile_size = compute_tile_size(MODEL_CONFIG["checkboxes"], preop_postop_image.size)
    detections_dict["checkboxes"] = detect_objects_using_tiling(
        preop_postop_image,
        CHECKBOXES_MODEL,
        tile_size,
        tile_size,
        MODEL_CONFIG["checkboxes"]["horz_overlap_proportion"],
        MODEL_CONFIG["checkboxes"]["vert_overlap_proportion"],
        nms_threshold=0.8,
    )

    return detections_dict


def assign_meaning_to_detections(
    detections_dict: Dict[str, List[Detection]],
) -> Dict[str, Any]:
    """Imputes values to the detections to get the data encoded by the provider onto the chart.

    Examples of assigning meaning include getting mmHg and timestamp values for blood pressure
    markers, assigning meaning to checked/unchecked checkbox detections, etc.

    Args:
        detections_dict (Dict[str, List[Detection]]):
            The detections from all models on both sides of the chart. Dictionary must match the
            template that is output by run_models.

    Returns:
        A dictionary with data that approximately matches the encoded meaning that the medical
        provider wrote onto the chart.
    """
    data: Dict[str, Any] = dict()
    data["intraoperative"] = assign_meaning_to_intraoperative_detections(
        detections_dict["intraoperative"]
    )
    data["preoperative_postoperative"] = (
        assign_meaning_to_preoperative_postoperative_detections(
            detections_dict["preoperative_postoperative"]
        )
    )
    return data


def assign_meaning_to_intraoperative_detections(
    intraop_detections_dict: Dict[str, List[Detection]],
    image_size: Tuple[int, int] = (3300, 2550),
) -> Dict[str, Any]:
    """Imputes values to the detections on the intraoperative side of the chart.

    Args:
        intraop_detections_dict (Dict[str, List[Detection]]):
            The detections from all models on the intraoperative side of the chart.
            Must match the template that is output by run_intraoperative_models.
        image_size (Tuple[int, int]):
            The size of the image.

    Returns:
        A dictionary with data that approximately matches the encoded meaning that the medical
        provider wrote onto the intraoperative side of the chart.
    """
    h = create_intraoperative_homography_matrix(intraop_detections_dict["landmarks"])
    corrected_detections_dict: Dict[str, List[Detection]] = dict()
    for key, detections in intraop_detections_dict.items():
        if len(detections) == 0:
            continue
        remap_func = (
            transform_box
            if isinstance(detections[0].annotation, BoundingBox)
            else transform_keypoint
        )
        corrected_detections_dict[key] = [
            Detection(remap_func(det.annotation, h), det.confidence)
            for det in detections
        ]

    extracted_data: Dict[str, Any] = dict()

    # extract drug code and surgical timing
    extracted_data["codes"] = extract_drug_codes(
        corrected_detections_dict["numbers"], *image_size
    )
    extracted_data["timing"] = extract_surgical_timing(
        corrected_detections_dict["numbers"], *image_size
    )
    extracted_data["ett_size"] = extract_ett_size(
        corrected_detections_dict["numbers"], *image_size
    )

    # extract inhaled volatile drugs
    time_boxes, mmhg_boxes = isolate_blood_pressure_legend_bounding_boxes(
        [det.annotation for det in corrected_detections_dict["landmarks"]], *image_size
    )
    time_clusters: List[Cluster] = cluster_boxes(
        time_boxes, cluster_kmeans, "mins", possible_nclusters=[40, 41, 42]
    )
    mmhg_clusters: List[Cluster] = cluster_boxes(
        mmhg_boxes, cluster_kmeans, "mmhg", possible_nclusters=[18, 19, 20]
    )

    legend_locations: Dict[str, Tuple[float, float]] = find_legend_locations(
        time_clusters + mmhg_clusters
    )
    extracted_data["inhaled_volatile"] = extract_inhaled_volatile(
        corrected_detections_dict["numbers"],
        legend_locations,
        corrected_detections_dict["landmarks"],
    )

    # extract bp and hr
    bp_and_hr_dets = reduce(
        concat,
        [
            corrected_detections_dict["systolic"],
            corrected_detections_dict["diastolic"],
            corrected_detections_dict["heart_rate"],
        ],
        list(),
    )

    extracted_data["bp_and_hr"] = extract_heart_rate_and_blood_pressure(
        bp_and_hr_dets,
        time_clusters,
        mmhg_clusters,
    )

    # extract physiological indicators
    extracted_data["physiological_indicators"] = extract_physiological_indicators(
        corrected_detections_dict["numbers"],
        legend_locations,
        corrected_detections_dict["landmarks"],
        *image_size
    )

    # extract checkboxes
    extracted_data["checkboxes"] = extract_checkboxes(
        corrected_detections_dict["checkboxes"],
        "intraoperative",
        image_size[0],
        image_size[1],
    )

    return extracted_data


def assign_meaning_to_preoperative_postoperative_detections(
    preop_postop_detections_dict: Dict[str, List[Detection]],
    image_size: Tuple[int, int] = (3300, 2550),
) -> Dict[str, Any]:
    """Imputes values to the detections on the preoperative/postoperative side of the chart.

    Args:
        intraop_detections_dict (Dict[str, List[Detection]]):
            The detections from all models on the preoperative/postoperative side of the chart.
            Must match the template that is output by run_intraoperative_models.

    Returns:
        A dictionary with data that approximately matches the encoded meaning that the medical
        provider wrote onto the preoperative/postoperative side of the chart.
    """
    h = create_preoperative_postoperative_homography_matrix(
        preop_postop_detections_dict["landmarks"]
    )
    corrected_detections_dict: Dict[str, List[Detection]] = dict()
    for key, detections in preop_postop_detections_dict.items():
        if len(detections) == 0:
            continue
        remap_func = (
            transform_box
            if isinstance(detections[0].annotation, BoundingBox)
            else transform_keypoint
        )
        corrected_detections_dict[key] = [
            Detection(remap_func(det.annotation, h), det.confidence)
            for det in detections
        ]

    extracted_data: Dict[str, Any] = dict()

    extracted_data.update(
        extract_preop_postop_digit_data(
            corrected_detections_dict["numbers"], *image_size
        )
    )
    extracted_data["checkboxes"] = extract_checkboxes(
        corrected_detections_dict["checkboxes"], "preoperative", *image_size
    )
    return extracted_data


def digitize_intraop_record(image: Image.Image) -> Dict:
    """Digitizes the intraoperative side of a paper anesthesia record.

    Args:
        `image` (Image.Image):
            The smartphone image of the intraoperative side of the
            paper anesthesia record.

    Returns:
        A dictionary containing all the data from the intraoperative side of
        the paper anesthesia record.
    """
    landmark_tile_size: int = compute_tile_size(
        MODEL_CONFIG["intraoperative_document_landmarks"], image.size
    )
    uncorrected_document_landmark_detections: List[Detection] = (
        detect_objects_using_tiling(
            image,
            INTRAOP_DOC_MODEL,
            landmark_tile_size,
            landmark_tile_size,
            MODEL_CONFIG["intraoperative_document_landmarks"][
                "horz_overlap_proportion"
            ],
            MODEL_CONFIG["intraoperative_document_landmarks"][
                "vert_overlap_proportion"
            ],
        )
    )
    image: Image.Image = homography_intraoperative_chart(
        image,
        uncorrected_document_landmark_detections,
    )
    document_landmark_detections: List[Detection] = detect_objects_using_tiling(
        image,
        INTRAOP_DOC_MODEL,
        landmark_tile_size,
        landmark_tile_size,
        MODEL_CONFIG["intraoperative_document_landmarks"]["horz_overlap_proportion"],
        MODEL_CONFIG["intraoperative_document_landmarks"]["vert_overlap_proportion"],
    )

    digit_tile_size: int = compute_tile_size(MODEL_CONFIG["numbers"], image.size)
    digit_detections: List[Detection] = detect_objects_using_tiling(
        image,
        NUMBERS_MODEL,
        digit_tile_size,
        digit_tile_size,
        MODEL_CONFIG["numbers"]["horz_overlap_proportion"],
        MODEL_CONFIG["numbers"]["vert_overlap_proportion"],
    )

    # extract drug code and surgical timing
    codes: Dict = {"codes": extract_drug_codes(digit_detections, *image.size)}
    times: Dict = {"timing": extract_surgical_timing(digit_detections, *image.size)}
    ett_size: Dict = {"ett_size": extract_ett_size(digit_detections, *image.size)}

    # extract inhaled volatile drugs
    time_boxes, mmhg_boxes = isolate_blood_pressure_legend_bounding_boxes(
        [det.annotation for det in document_landmark_detections], *image.size
    )
    time_clusters: List[Cluster] = cluster_boxes(
        time_boxes, cluster_kmeans, "mins", possible_nclusters=[40, 41, 42]
    )
    mmhg_clusters: List[Cluster] = cluster_boxes(
        mmhg_boxes, cluster_kmeans, "mmhg", possible_nclusters=[18, 19, 20]
    )

    legend_locations: Dict[str, Tuple[float, float]] = find_legend_locations(
        time_clusters + mmhg_clusters
    )

    inhaled_volatile: Dict = {
        "inhaled_volatile": extract_inhaled_volatile(
            digit_detections, legend_locations, document_landmark_detections
        )
    }

    # extract bp and hr
    bp_and_hr: Dict = {
        "bp_and_hr": make_bp_and_hr_detections(image, time_clusters, mmhg_clusters)
    }

    # extract physiological indicators
    physiological_indicators: Dict = {
        "physiological_indicators": extract_physiological_indicators(
            digit_detections,
            legend_locations,
            document_landmark_detections,
            *image.size
        )
    }

    # extract checkboxes
    checkboxes: Dict = {
        "intraoperative_checkboxes": make_intraop_checkbox_detections(image)
    }

    return combine_dictionaries(
        [
            codes,
            times,
            ett_size,
            inhaled_volatile,
            bp_and_hr,
            physiological_indicators,
            checkboxes,
        ]
    )


def digitize_preop_postop_record(image: Image.Image) -> Dict:
    """Digitizes the preoperative/postoperative side of a paper anesthesia record.

    Args:
        `image` (Image.Image):
            The smartphone image of the preoperative/postopeerative
            side of the paper anesthesia record.

    Returns:
        A dictionary containing all the data from the preoperative/postoperative
        side of the paper anesthesia record.
    """
    landmark_tile_size: int = compute_tile_size(
        MODEL_CONFIG["preop_postop_document_landmarks"],
        image.size,
    )
    document_landmark_detections: List[Detection] = detect_objects_using_tiling(
        image,
        PREOP_POSTOP_DOC_MODEL,
        landmark_tile_size,
        landmark_tile_size,
        MODEL_CONFIG["preop_postop_document_landmarks"]["horz_overlap_proportion"],
        MODEL_CONFIG["preop_postop_document_landmarks"]["vert_overlap_proportion"],
    )
    image: Image.Image = homography_preoperative_chart(
        image, document_landmark_detections
    )
    digit_tile_size: int = compute_tile_size(MODEL_CONFIG["numbers"], image.size)
    digit_detections: List[Detection] = detect_objects_using_tiling(
        image,
        NUMBERS_MODEL,
        digit_tile_size,
        digit_tile_size,
        MODEL_CONFIG["numbers"]["horz_overlap_proportion"],
        MODEL_CONFIG["numbers"]["vert_overlap_proportion"],
    )
    digit_data = extract_preop_postop_digit_data(digit_detections, *image.size)
    checkbox_data = {
        "preoperative_checkboxes": make_preop_postop_checkbox_detections(image)
    }
    return combine_dictionaries([digit_data, checkbox_data])


def create_homography_matrix(
    landmark_detections: List[Detection],
    corner_landmark_names: List[str],
    destination_landmarks: List[BoundingBox],
) -> np.ndarray:
    """Creates a homography matrix from the corner landmarks.

    Args:
        landmark_detections (List[Detection]):
            The list of detected landmarks.
        corner_landmark_names (List[str]):
            The list of names that match categories from the landmark detections.
        destination_landmarks (List[BoundingBox]):
            The landmark locations on the perfect, scanned image.

    Returns:
        A homography matrix that linearly transforms points from the original image to the
        scanned, perfect image.
    """
    dest_points = [
        bb.center
        for bb in sorted(
            list(
                filter(
                    lambda x: x.category in corner_landmark_names, destination_landmarks
                )
            ),
            key=lambda bb: bb.category,
        )
    ]
    src_points = [
        bb.annotation.center
        for bb in sorted(
            list(
                filter(
                    lambda x: x.annotation.category in corner_landmark_names,
                    landmark_detections,
                )
            ),
            key=lambda bb: bb.annotation.category,
        )
    ]
    return find_homography(src_points, dest_points)


def create_intraoperative_homography_matrix(
    landmark_detections: List[Detection],
) -> np.ndarray:
    """Creates a homography matrix for the intraoperative side of the chart.

    Args:
        landmark_detections (List[Detection]):
            The list of detected landmarks.

    Returns:
        A homography matrix that linearly transforms points from the original image to the
        scanned, perfect image.
    """
    corner_landmark_names: List[str] = [
        "anesthesia_start",
        "safety_checklist",
        "lateral",
        "units",
    ]
    dst_landmarks: List[BoundingBox] = label_studio_to_bboxes(
        str(PATH_TO_DATA / "intraop_document_landmarks.json")
    )["unified_intraoperative_preoperative_flowsheet_v1_1_front.png"]
    return create_homography_matrix(
        landmark_detections, corner_landmark_names, dst_landmarks
    )


def create_preoperative_postoperative_homography_matrix(
    landmark_detections: List[Detection],
) -> np.ndarray:
    """Creates a homography matrix for the intraoperative side of the chart.

    Args:
        landmark_detections (List[Detection]):
            The list of detected landmarks.

    Returns:
        A homography matrix that linearly transforms points from the original image to the
        scanned, perfect image.
    """
    corner_landmark_names: List[str] = [
        "patient_profile",
        "weight",
        "signature",
        "disposition",
    ]
    dst_landmarks: List[BoundingBox] = label_studio_to_bboxes(
        str(PATH_TO_DATA / "preoperative_document_landmarks.json")
    )["unified_intraoperative_preoperative_flowsheet_v1_1_back.png"]
    return create_homography_matrix(
        landmark_detections, corner_landmark_names, dst_landmarks
    )


def homography_intraoperative_chart(
    image: Image.Image,
    intraop_document_detections: List[Detection],
) -> Image.Image:
    """Performs a homography transformation on the intraoperative side of the chart.

    Args:
        `image` (Image.Image):
            The intraoperative image to transform.
        `intraop_document_detections` (List[Detection]):
            The locations of the document landmarks.

    Returns:
        An image that is warped to correct the locations of objects on the image.
    """
    corner_landmark_names: List[str] = [
        "anesthesia_start",
        "safety_checklist",
        "lateral",
        "units",
    ]
    dst_landmarks = label_studio_to_bboxes(
        str(PATH_TO_DATA / "intraop_document_landmarks.json")
    )["unified_intraoperative_preoperative_flowsheet_v1_1_front.png"]

    dest_points = [
        bb.center
        for bb in sorted(
            list(filter(lambda x: x.category in corner_landmark_names, dst_landmarks)),
            key=lambda bb: bb.category,
        )
    ]
    src_points = [
        bb.annotation.center
        for bb in sorted(
            list(
                filter(
                    lambda x: x.annotation.category in corner_landmark_names,
                    intraop_document_detections,
                )
            ),
            key=lambda bb: bb.annotation.category,
        )
    ]
    return homography_transform(
        image,
        dest_points=dest_points,
        src_points=src_points,
        original_image_size=(3300, 2550),
    )


def homography_preoperative_chart(
    image: Image.Image,
    preop_document_detections: List[Detection],
) -> Image.Image:
    """Performs a homography transformation on the preop/postop side of the chart.

    Args:
        `image` (Image.Image):
            The preoperative/postoperative image to transform.
        `preop_document_detections` (List[Detection]):
            The locations of the document landmarks.

    Returns:
        An image that is warped to correct the locations of objects on the image.
    """
    corner_landmark_names: List[str] = [
        "patient_profile",
        "weight",
        "signature",
        "disposition",
    ]
    dst_landmarks = label_studio_to_bboxes(
        str(PATH_TO_DATA / "preoperative_document_landmarks.json")
    )["unified_intraoperative_preoperative_flowsheet_v1_1_back.png"]

    dest_points = [
        bb.center
        for bb in sorted(
            list(filter(lambda x: x.category in corner_landmark_names, dst_landmarks)),
            key=lambda bb: bb.category,
        )
    ]
    src_points = [
        bb.annotation.center
        for bb in sorted(
            list(
                filter(
                    lambda x: x.annotation.category in corner_landmark_names,
                    preop_document_detections,
                )
            ),
            key=lambda bb: bb.annotation.category,
        )
    ]
    return homography_transform(
        image,
        dest_points=dest_points,
        src_points=src_points,
        original_image_size=(3300, 2550),
    )


def compute_tile_size(model_config: Dict, image_size: Tuple[int, int]) -> int:
    """Finds the tile size for a model based on how its training dataset was generated.

    Args:
        model_config (Dict):
            The model's config dictionary.
        image_size (Tuple[int, int])
    """
    tile_size_proportion = model_config["tile_size_proportion"]
    tile_size: int = int(
        min(
            image_size[0] * tile_size_proportion,
            image_size[1] * tile_size_proportion,
        )
    )
    return tile_size


def make_bp_and_hr_detections(
    image: Image.Image,
    time_clusters: List[Cluster],
    mmhg_clusters: List[Cluster],
) -> Dict:
    """Finds blood pressure symbols and associates a value and timestamp to them.

    Args:
        `image` (Image.Image):
            The image to detect on.
        `time_clusters` (List[Cluster]):
            A list of Cluster objects encoding the location of the time legend.
        `mmhg_clusters` (List[Cluster]):
            A list of Cluster objects encoding the location of the mmhg/bpm legend.

    Returns:
        A dictionary mapping timestamps to values for systolic, diastolic, and heart rate.
    """
    sys_tile_size: int = compute_tile_size(MODEL_CONFIG["systolic"], image.size)
    dia_tile_size: int = compute_tile_size(MODEL_CONFIG["diastolic"], image.size)
    hr_tile_size: int = compute_tile_size(MODEL_CONFIG["heart_rate"], image.size)

    sys_dets: List[Detection] = detect_objects_using_tiling(
        image.copy(),
        SYSTOLIC_MODEL,
        sys_tile_size,
        sys_tile_size,
        MODEL_CONFIG["systolic"]["horz_overlap_proportion"],
        MODEL_CONFIG["systolic"]["vert_overlap_proportion"],
    )
    dia_dets: List[Detection] = detect_objects_using_tiling(
        image.copy(),
        DIASTOLIC_MODEL,
        dia_tile_size,
        dia_tile_size,
        MODEL_CONFIG["diastolic"]["horz_overlap_proportion"],
        MODEL_CONFIG["diastolic"]["vert_overlap_proportion"],
    )
    hr_dets: List[Detection] = detect_objects_using_tiling(
        image.copy(),
        HEART_RATE_MODEL,
        hr_tile_size,
        hr_tile_size,
        MODEL_CONFIG["heart_rate"]["horz_overlap_proportion"],
        MODEL_CONFIG["heart_rate"]["vert_overlap_proportion"],
    )

    dets: List[Detection] = sys_dets + dia_dets + hr_dets
    bp_and_hr = extract_heart_rate_and_blood_pressure(
        dets, time_clusters, mmhg_clusters
    )
    return bp_and_hr


def make_intraop_checkbox_detections(image: Image.Image) -> Dict:
    """Finds checkboxes on the intraoperative form, then associates a meaning to them.

    Args:
        `image` (Image.Image):
            The image to detect on.

    Returns:
        A dictionary mapping names of checkboxes to a "checked" or "unchecked" state.
    """
    tile_size = compute_tile_size(MODEL_CONFIG["checkboxes"], image.size)
    detections: List[Detection] = detect_objects_using_tiling(
        image,
        CHECKBOXES_MODEL,
        tile_size,
        tile_size,
        MODEL_CONFIG["checkboxes"]["horz_overlap_proportion"],
        MODEL_CONFIG["checkboxes"]["vert_overlap_proportion"],
        nms_threshold=0.8,
    )
    intraop_checkboxes = extract_checkboxes(
        detections,
        "intraoperative",
        image.size[0],
        image.size[1],
    )
    return intraop_checkboxes


def make_preop_postop_checkbox_detections(image: Image.Image):
    """Finds checkboxes on the intraoperative form, then associates a meaning to them.

    Args:
        `image` (Image.Image):
            The image to detect on.

    Returns:
        A dictionary mapping names of checkboxes to a "checked" or "unchecked" state.
    """
    tile_size = compute_tile_size(MODEL_CONFIG["checkboxes"], image.size)
    detections: List[Detection] = detect_objects_using_tiling(
        image,
        CHECKBOXES_MODEL,
        tile_size,
        tile_size,
        MODEL_CONFIG["checkboxes"]["horz_overlap_proportion"],
        MODEL_CONFIG["checkboxes"]["vert_overlap_proportion"],
        nms_threshold=0.8,
    )
    preop_postop_checkboxes = extract_checkboxes(
        detections,
        "preoperative",
        image.size[0],
        image.size[1],
    )
    return preop_postop_checkboxes
