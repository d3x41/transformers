# coding=utf-8
# Copyright 2025 Deepseek AI and The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from typing import Optional, Union

from ...image_processing_utils import BatchFeature
from ...image_processing_utils_fast import (
    BaseImageProcessorFast,
    DefaultFastImageProcessorKwargs,
    group_images_by_shape,
    reorder_images,
)
from ...image_utils import (
    OPENAI_CLIP_MEAN,
    OPENAI_CLIP_STD,
    ImageInput,
    PILImageResampling,
    SizeDict,
)
from ...processing_utils import Unpack
from ...utils import (
    TensorType,
    auto_docstring,
    is_torch_available,
    is_torchvision_available,
    is_torchvision_v2_available,
)


if is_torch_available():
    import torch
if is_torchvision_v2_available():
    from torchvision.transforms.v2 import functional as F
elif is_torchvision_available():
    from torchvision.transforms import functional as F


class JanusFastImageProcessorKwargs(DefaultFastImageProcessorKwargs):
    r"""
    min_size (`int`, *optional*, defaults to 14):
        The minimum allowed size for the resized image. Ensures that neither the height nor width
        falls below this value after resizing.
    """

    min_size: int


@auto_docstring
class JanusImageProcessorFast(BaseImageProcessorFast):
    resample = PILImageResampling.BICUBIC
    image_mean = OPENAI_CLIP_MEAN
    image_std = OPENAI_CLIP_STD
    size = {"height": 384, "width": 384}
    min_size = 14
    do_resize = True
    do_rescale = True
    do_normalize = True
    valid_kwargs = JanusFastImageProcessorKwargs

    def __init__(self, **kwargs: Unpack[JanusFastImageProcessorKwargs]):
        if kwargs.get("image_mean", None) is None:
            background_color = (127, 127, 127)
        else:
            background_color = tuple([int(x * 255) for x in kwargs.get("image_mean")])
        super().__init__(**kwargs)
        self.background_color = tuple(background_color)

    def resize(
        self,
        image: "torch.Tensor",
        size: SizeDict,
        min_size: int,
        interpolation: "F.InterpolationMode" = None,
        antialias: bool = True,
        **kwargs,
    ) -> "torch.Tensor":
        if size.height is None or size.width is None or size.height != size.width:
            raise ValueError(
                f"Output height and width must be the same. Got height={size['height']} and width={size['width']}"
            )
        size = size.height

        height, width = image.shape[-2:]
        max_size = max(height, width)

        delta = size / max_size
        # Largest side becomes `size` and the other side is scaled according to the aspect ratio.
        output_size_nonpadded = SizeDict(
            height=max(int(height * delta), min_size),
            width=max(int(width * delta), min_size),
        )

        return super().resize(image, size=output_size_nonpadded, interpolation=interpolation, antialias=antialias)

    def pad_to_square(
        self,
        images: "torch.Tensor",
        background_color: Union[int, tuple[int, int, int]] = 0,
    ) -> "torch.Tensor":
        """
        Pads an image to a square based on the longest edge.

        Args:
            images (`torch.Tensor`):
                The images to pad.
            background_color (`int` or `tuple[int, int, int]`, *optional*, defaults to 0):
                The color to use for the padding. Can be an integer for single channel or a
                tuple of integers representing for multi-channel images. If passed as integer
                in mutli-channel mode, it will default to `0` in subsequent channels.

        Returns:
            `torch.Tensor`: The padded images.
        """
        height, width = images.shape[-2:]
        num_channels = images.shape[1]
        batch_size = images.shape[0]

        if height == width:
            return images

        max_dim = max(height, width)

        # Ensure background_color is the correct shape
        if isinstance(background_color, int):
            background_color = [background_color]
        elif len(background_color) != num_channels:
            raise ValueError(
                f"background_color must have no more than {num_channels} elements to match the number of channels"
            )

        padded_images = torch.zeros(
            (batch_size, num_channels, max_dim, max_dim), dtype=images.dtype, device=images.device
        )
        for i, color in enumerate(background_color):
            padded_images[:, i, :, :] = color
        if width > height:
            start = (max_dim - height) // 2
            padded_images[:, :, start : start + height, :] = images
        else:
            start = (max_dim - width) // 2
            padded_images[:, :, :, start : start + width] = images

        return padded_images

    def _preprocess(
        self,
        images: list["torch.Tensor"],
        do_resize: bool,
        size: SizeDict,
        min_size: int,
        interpolation: Optional["F.InterpolationMode"],
        do_rescale: bool,
        rescale_factor: float,
        do_normalize: bool,
        image_mean: Optional[Union[float, list[float]]],
        image_std: Optional[Union[float, list[float]]],
        disable_grouping: Optional[bool],
        return_tensors: Optional[Union[str, TensorType]],
        do_pad: bool = True,
        **kwargs,
    ) -> BatchFeature:
        # Group images by size for batched resizing
        grouped_images, grouped_images_index = group_images_by_shape(images, disable_grouping=disable_grouping)
        resized_images_grouped = {}
        for shape, stacked_images in grouped_images.items():
            if do_resize:
                stacked_images = self.resize(
                    image=stacked_images, size=size, min_size=min_size, interpolation=interpolation
                )
            resized_images_grouped[shape] = stacked_images
        resized_images = reorder_images(resized_images_grouped, grouped_images_index)

        # Group images by size for further processing
        # Needed in case do_resize is False, or resize returns images with different sizes
        grouped_images, grouped_images_index = group_images_by_shape(resized_images, disable_grouping=disable_grouping)
        processed_images_grouped = {}
        for shape, stacked_images in grouped_images.items():
            if do_pad:
                stacked_images = self.pad_to_square(stacked_images, background_color=self.background_color)
            # Fused rescale and normalize
            stacked_images = self.rescale_and_normalize(
                stacked_images, do_rescale, rescale_factor, do_normalize, image_mean, image_std
            )
            processed_images_grouped[shape] = stacked_images

        processed_images = reorder_images(processed_images_grouped, grouped_images_index)
        processed_images = torch.stack(processed_images, dim=0) if return_tensors else processed_images

        return BatchFeature(data={"pixel_values": processed_images}, tensor_type=return_tensors)

    def postprocess(
        self,
        images: ImageInput,
        do_rescale: Optional[bool] = None,
        rescale_factor: Optional[float] = None,
        do_normalize: Optional[bool] = None,
        image_mean: Optional[list[float]] = None,
        image_std: Optional[list[float]] = None,
        return_tensors: Optional[str] = None,
    ) -> "torch.Tensor":
        do_rescale = do_rescale if do_rescale is not None else self.do_rescale
        rescale_factor = 1.0 / self.rescale_factor if rescale_factor is None else rescale_factor
        do_normalize = do_normalize if do_normalize is not None else self.do_normalize
        image_mean = image_mean if image_mean is not None else self.image_mean
        image_std = image_std if image_std is not None else self.image_std
        image_mean = tuple(-rescale_factor * mean / std for mean, std in zip(image_mean, image_std))
        image_std = tuple(1 / std for std in image_std)

        images = self.preprocess(
            images,
            do_rescale=do_rescale,
            rescale_factor=rescale_factor,
            do_normalize=do_normalize,
            image_mean=image_mean,
            image_std=image_std,
            do_resize=False,
            do_pad=False,
            return_tensors=return_tensors,
        ).pixel_values
        if do_rescale:
            images = [image.clip(0, 255).to(torch.uint8) for image in images]

        if do_normalize and do_rescale and return_tensors == "PIL.Image.Image":
            images = [F.to_pil_image(image) for image in images]

        data = {"pixel_values": images}
        return_tensors = return_tensors if return_tensors != "PIL.Image.Image" else None

        return BatchFeature(data=data, tensor_type=return_tensors)


__all__ = ["JanusImageProcessorFast"]
