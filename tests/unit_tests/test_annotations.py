"""Tests for the annotations module."""

# External Imports
import pytest

# Internal Imports
from ChartExtractor.utilities.annotations import BoundingBox, Keypoint, Point


class TestBoundingBox:
    """Tests the BoundingBox class."""

    # Init
    def test_init(self):
        """Tests the init function with valid parameters."""
        BoundingBox("Test", 0, 0, 1, 1)
    
    def test_from_dict(self):
        """Tests the from_dict constructor."""
        bb_dict = {
            "left": 1,
            "right": 2,
            "top": 3,
            "bottom": 4,
            "category": "Test"
        }
        true_bbox = BoundingBox("Test", 1, 3, 2, 4)
        assert BoundingBox.from_dict(bb_dict) == true_bbox

    def test_from_dict_fails(self):
        """Tests the from_dict constructor when the dictionary contains an erroneous entry."""
        bb_dict = {
            "left": 1,
            "right": 2,
            "top": 3,
            "bottom": 4,
            "category": "Test",
            "other": "thing"
        }
        with pytest.raises(TypeError):
            BoundingBox.from_dict(bb_dict)

    # from_yolo
    def test_from_yolo(self):
        """Tests the from_yolo constructor."""
        true_bbox = BoundingBox("Test", 0, 0, 1, 1)
        yolo_line = "0 0.25 0.25 0.5 0.5"
        image_width = 2
        image_height = 2
        id_to_category = {0: "Test"}
        created_bbox = BoundingBox.from_yolo(
            yolo_line, image_width, image_height, id_to_category
        )
        assert true_bbox == created_bbox

    def test_from_yolo_category_not_in_id_to_category_dict(self):
        """Tests the from_yolo constructor where the supplied id is not in the id_to_category dictionary."""
        yolo_line = "0 0.25 0.25 0.5 0.5"
        image_width = 2
        image_height = 2
        id_to_category = {1: "Test"}
        with pytest.raises(
            ValueError, match="not found in the id_to_category dictionary"
        ):
            BoundingBox.from_yolo(yolo_line, image_width, image_height, id_to_category)

    # from_coco
    def test_from_coco(self):
        """Tests the from_coco constructor."""
        true_bbox = BoundingBox("Test", 0, 0, 1, 1)
        coco_annotation = {
            "id": 0,
            "image_id": 0,
            "category_id": 0,
            "bbox": [0, 0, 1, 1],
        }
        categories = [{"id": 0, "name": "Test"}]
        created_bbox = BoundingBox.from_coco(coco_annotation, categories)
        assert true_bbox == created_bbox

    def test_from_coco_category_not_found_in_(self):
        """Tests the from_coco constructor where the supplied category is not in the list of category dictionaries."""
        coco_annotation = {
            "id": 0,
            "image_id": 0,
            "category_id": 0,
            "bbox": [0, 0, 1, 1],
        }
        categories = [{"id": 1, "name": "Test"}]
        with pytest.raises(ValueError, match="not found in the categories list"):
            BoundingBox.from_coco(coco_annotation, categories)

    # validate_box_values
    def test_validate_box_values_left_greater_than_right(self):
        """Tests the validate_box_values classmethod with invalid parameters (left > right)."""
        with pytest.raises(ValueError, match="left side greater than its right side"):
            BoundingBox("Test", 1, 0, 0, 1)

    def test_validate_box_values_top_greater_than_bottom(self):
        """Tests the validate_box_values classmethod with invalid parameters (top > bottom)."""
        with pytest.raises(ValueError, match="top side greater than its bottom side"):
            BoundingBox("Test", 0, 1, 1, 0)

    def test_validate_box_values_left_eq_right(self):
        """Tests the validate_box_values classmethod with degenerate rectangle parameters (left == right)."""
        with pytest.warns(UserWarning, match="left side equals its right side"):
            BoundingBox("Test", 0, 0, 0, 1)

    def test_validate_box_values_top_eq_bottom(self):
        """Tests the validate_box_values classmethod with degenerate rectangle parameters (top == bottom)."""
        with pytest.warns(UserWarning, match="top side equals its bottom side"):
            BoundingBox("Test", 0, 0, 1, 0)

    def test_validate_box_values_left_eq_right_top_eq_bottom(self):
        """Tests the validate_box_values classmethod with degernate rectangle parameters (left == right == top == bottom)."""
        with pytest.warns(UserWarning, match="box's parameters are equal"):
            BoundingBox("Test", 0, 0, 0, 0)

    # Center
    def test_center(self):
        """Tests the 'center' property."""
        bbox = BoundingBox("Test", 0, 0, 1, 1)
        assert (0.5, 0.5) == bbox.center

    # Box
    def test_box(self):
        """Tests the 'box' property."""
        bbox = BoundingBox("Test", 0, 0, 1, 1)
        assert [0, 0, 1, 1] == bbox.box
    
    def test_to_dict(self):
        """Tests the to_dict method."""
        bbox = BoundingBox("Test", 0, 2, 1, 3)
        true_dict = {
            "left": 0,
            "right": 1,
            "top": 2,
            "bottom": 3,
            "category": "Test"
        }
        assert bbox.to_dict() == true_dict

    # to_yolo
    def test_to_yolo(self):
        """Tests the to_yolo method."""
        bbox = BoundingBox("Test", 0, 0, 1, 1)
        image_width = 2
        image_height = 2
        category_to_id = {"Test": 0}
        yolo_str = bbox.to_yolo(image_width, image_height, category_to_id, 3)
        assert yolo_str == "0 0.250 0.250 0.500 0.500"


class TestKeypoint:
    """Tests the Keypoint class."""

    # Init
    def test_init(self):
        """Tests the init function with valid parameters."""
        kp = Point(0.25, 0.25)
        bbox = BoundingBox("Test", 0, 0, 1, 1)
        Keypoint(kp, bbox)
    
    def test_from_dict(self):
        """Test the from_dict constructor."""
        keypoint_dict = {
            "keypoint": {
                "x": 0.5,
                "y": 2.25,
            },
            "bounding_box": {
                "left": 0,
                "right": 1,
                "top": 2,
                "bottom": 3,
                "category": "Test"
            },
        }
        true_point = Point(0.5, 2.25)
        true_bounding_box = BoundingBox("Test", 0, 2, 1, 3)
        true_keypoint = Keypoint(true_point, true_bounding_box)
        assert Keypoint.from_dict(keypoint_dict) == true_keypoint
    
    # from_yolo
    def test_from_yolo(self):
        """Tests the from_yolo constructor."""
        true_kp = Keypoint(Point(0.25, 0.25), BoundingBox("Test", 0, 0, 1, 1))
        yolo_line = "0 0.25 0.25 0.5 0.5 0.125 0.125"
        image_width = 2
        image_height = 2
        id_to_category = {0: "Test"}
        created_kp = Keypoint.from_yolo(
            yolo_line, image_width, image_height, id_to_category
        )
        assert true_kp == created_kp

    # validate_keyoint
    def test_validate_keypoint_out_of_bounds_x(self):
        """Tests the validate_keypoint method where the keypoint is not within the left-right bounds."""
        # Left of box.
        with pytest.raises(ValueError, match="not in the bounding box"):
            Keypoint(Point(1, 1), BoundingBox("Test", 2, 0, 3, 2))
        # Right of box.
        with pytest.raises(ValueError, match="not in the bounding box"):
            Keypoint(Point(4, 1), BoundingBox("Test", 2, 0, 3, 2))

    def test_validate_keypoint_out_of_bounds_y(self):
        """Tests the validate_keypoint method where the keypoint is not within the left-right bounds."""
        # Above box
        with pytest.raises(ValueError):
            Keypoint(Point(1, 1), BoundingBox("Test", 0, 2, 2, 3))
        # Below box
        with pytest.raises(ValueError):
            Keypoint(Point(1, 4), BoundingBox("Test", 0, 2, 2, 3))
    
    def test_to_dict(self):
        """Tests the to_dict method."""
        point = Point(0.5, 2.25)
        bbox = BoundingBox("Test", 0, 2, 1, 3)
        kp = Keypoint(point, bbox)
        kp_dict = kp.to_dict()
        true_dict = {
            "keypoint": {
                "x": 0.5,
                "y": 2.25,
            },
            "bounding_box": {
                "left": 0,
                "top": 2,
                "right": 1,
                "bottom": 3,
                "category": "Test",
            },
        }
        assert kp_dict == true_dict

    # to_yolo
    def test_to_yolo(self):
        """Tests the to_yolo method."""
        kp = Keypoint(Point(0.25, 0.25), BoundingBox("Test", 0, 0, 1, 1))
        image_width = 2
        image_height = 2
        category_to_id = {"Test": 0}
        yolo_str = kp.to_yolo(image_width, image_height, category_to_id, 3)
        assert yolo_str == "0 0.250 0.250 0.500 0.500 0.125 0.125"
