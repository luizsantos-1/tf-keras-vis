from typing import Union

import numpy as np
import tensorflow as tf
import tensorflow.keras.backend as K
from scipy.ndimage.interpolation import zoom

from . import ModelVisualization
from .utils import get_num_of_steps_allowed, is_mixed_precision, listify, standardize, zoom_factor
from .utils.model_modifiers import ExtractIntermediateLayerForGradcam as ModelModifier


class Scorecam(ModelVisualization):
    """Score-CAM and Faster Score-CAM

        For details on Score-CAM, see the paper:
        [Score-CAM: Score-Weighted Visual Explanations for Convolutional Neural Networks ]
        (https://arxiv.org/pdf/1910.01279.pdf).

        For details on Faster Score-CAM, see the web site:
        https://github.com/tabayashi0117/Score-CAM#faster-score-cam
    Todo:
        * Write examples
    """
    def __call__(self,
                 score,
                 seed_input,
                 penultimate_layer=-1,
                 seek_penultimate_conv_layer=True,
                 activation_modifier=lambda cam: K.relu(cam),
                 batch_size=32,
                 max_N=None,
                 training=False,
                 expand_cam=True,
                 standardize_cam=True) -> Union[np.ndarray, list]:
        """Generate score-weighted class activation maps (CAM)
            by using gradient-free visualization method.

        Args:
            score (Union[tf_keras_vis.utils.scores.Score,Callable,
                list[tf_keras_vis.utils.scores.Score,Callable]]):
                A Score instance or function to specify visualizing target. For example::

                    scores = CategoricalScore([1, 294, 413])

                This code above means the same with the one below::

                    score = lambda outputs: (outputs[0][1], outputs[1][294], outputs[2][413])

                When the model has multiple outputs, you have to pass a list of
                Score instances or functions. For example::

                    score = [
                        tf_keras_vis.utils.scores.CategoricalScore([1, 23]),  # For 1st output
                        tf_keras_vis.utils.scores.InactiveScore(),            # For 2nd output
                        ...
                    ]

            seed_input (Union[tf.Tensor,np.ndarray,list[tf.Tensor,np.ndarray]]):
                A tensor or a list of them to input in the model.
                When the model has multiple inputs, you have to pass a list.
            penultimate_layer (Union[int,str,tf.keras.layers.Layer], optional):
                An index of the layer or the name of it or the instance itself.
                When None, it means the same as -1.
                If the layer specified by `penultimate_layer` is not `convolutional` layer,
                `penultimate_layer` will work as the offset to seek `convolutional` layer.
                Defaults to None.
            seek_penultimate_conv_layer (bool, optional):
                A bool that indicates whether seeks a penultimate layer or not
                when the layer specified by `penultimate_layer` is not `convolutional` layer.
                Defaults to True.
            activation_modifier (Callable, optional):  A function to modify activation.
                Defaults to `lambda cam: K.relu(cam)`.
            batch_size (int, optional): The number of samples per batch. Defaults to 32.
            max_N (int, optional): Setting None or under Zero is that we do NOT recommend,
                because it takes a long time to calculate CAM.
                When not None or over Zero of Integer, run as Faster-ScoreCAM.
                Set larger number, need more time to visualize CAM
                but to be able to get clearer attention images.
                (see for details: https://github.com/tabayashi0117/Score-CAM#faster-score-cam)
                Defaults to None.
            training (bool, optional): A bool that indicates
                whether the model's training-mode on or off. Defaults to False.
            expand_cam (bool, optional): True to resize cam to the same as input image size.
                ![Note] When True, even if the model has multiple inputs,
                this function return only a cam value (That's, when `expand_cam` is True,
                multiple cam images are generated from a model that has multiple inputs).
            standardize_cam (bool, optional): When True, cam will be standardized.
                Defaults to True.

        Returns:
            Union[np.ndarray,list]: The class activation maps that indicate the `seed_input` regions
                whose change would most contribute the score value.

        Raises:
            ValueError: In case of invalid arguments for `score`, or `penultimate_layer`.
        """
        # Preparing
        scores = self._get_scores_for_multiple_outputs(score)
        seed_inputs = self._get_seed_inputs_for_multiple_inputs(seed_input)

        # Processing score-cam
        model = ModelModifier(penultimate_layer, seek_penultimate_conv_layer, False)(self.model)
        penultimate_output = model(seed_inputs, training=training)

        if is_mixed_precision(self.model):
            penultimate_output = tf.cast(penultimate_output, self.model.variable_dtype)

        # For efficiently visualizing, extract maps that has a large variance.
        # This excellent idea is devised by tabayashi0117.
        # (see for details: https://github.com/tabayashi0117/Score-CAM#faster-score-cam)
        if max_N is None or max_N == -1:
            max_N = get_num_of_steps_allowed(penultimate_output.shape[-1])
        elif max_N == 0:
            raise ValueError("max_N can't be set 0, must be None, -1 or 1 or more.")
        else:
            max_N = get_num_of_steps_allowed(max_N)
        if max_N < penultimate_output.shape[-1]:
            activation_map_std = tf.math.reduce_std(penultimate_output,
                                                    axis=tuple(
                                                        range(penultimate_output.ndim)[1:-1]),
                                                    keepdims=True)
            _, top_k_indices = tf.math.top_k(activation_map_std, max_N)
            top_k_indices, _ = tf.unique(tf.reshape(top_k_indices, (-1, )))
            penultimate_output = tf.gather(penultimate_output, top_k_indices, axis=-1)
        channels = penultimate_output.shape[-1]

        # Upsampling activation-maps
        input_shapes = [seed_input.shape for seed_input in seed_inputs]
        factors = (zoom_factor(penultimate_output.shape[:-1], input_shape[:-1])
                   for input_shape in input_shapes)
        upsampled_activation_maps = [zoom(penultimate_output, factor + (1, )) for factor in factors]
        map_shapes = [activation_map.shape for activation_map in upsampled_activation_maps]

        # Normalizing activation-maps
        min_activation_maps = (np.min(activation_map,
                                      axis=tuple(range(activation_map.ndim)[1:-1]),
                                      keepdims=True)
                               for activation_map in upsampled_activation_maps)
        max_activation_maps = (np.max(activation_map,
                                      axis=tuple(range(activation_map.ndim)[1:-1]),
                                      keepdims=True)
                               for activation_map in upsampled_activation_maps)
        normalized_activation_maps = (
            (activation_map - min_activation_map) /
            (max_activation_map - min_activation_map + K.epsilon())
            for activation_map, min_activation_map, max_activation_map in zip(
                upsampled_activation_maps, min_activation_maps, max_activation_maps))

        # Masking inputs
        input_tile_axes = ((map_shape[-1], ) + tuple(np.ones(len(input_shape), np.int))
                           for input_shape, map_shape in zip(input_shapes, map_shapes))
        mask_templates = (np.tile(seed_input, axes)
                          for seed_input, axes in zip(seed_inputs, input_tile_axes))
        map_transpose_axes = ((len(map_shape) - 1, ) + tuple(range(len(map_shape))[:-1])
                              for map_shape in map_shapes)
        masks = (np.transpose(activation_map,
                              transpose_axis) for activation_map, transpose_axis in zip(
                                  normalized_activation_maps, map_transpose_axes))
        map_tile_axes = (tuple(np.ones(len(map_shape), np.int)) + (input_shape[-1], )
                         for input_shape, map_shape in zip(input_shapes, map_shapes))
        masks = (np.tile(np.expand_dims(activation_map, axis=-1), tile_axis)
                 for activation_map, tile_axis in zip(masks, map_tile_axes))
        masked_seed_inputs = (mask_template * mask
                              for mask_template, mask in zip(mask_templates, masks))
        masked_seed_inputs = [
            np.reshape(masked_seed_input, (-1, ) + masked_seed_input.shape[2:])
            for masked_seed_input in masked_seed_inputs
        ]

        # Predicting masked seed-inputs
        preds = self.model.predict(masked_seed_inputs, batch_size=batch_size)
        preds = (np.reshape(prediction, (channels, -1, prediction.shape[-1]))
                 for prediction in listify(preds))

        # Calculating weights
        weights = ([score(p) for p in prediction] for score, prediction in zip(scores, preds))
        weights = (np.array(w, dtype=np.float32) for w in weights)
        weights = (np.reshape(w, (penultimate_output.shape[0], -1, channels)) for w in weights)
        weights = (np.mean(w, axis=1) for w in weights)
        weights = np.array(list(weights), dtype=np.float32)
        weights = np.sum(weights, axis=0)

        # Generate cam
        cam = K.batch_dot(penultimate_output, weights)
        if activation_modifier is not None:
            cam = activation_modifier(cam)

        if not expand_cam:
            if standardize_cam:
                cam = standardize(cam)
            return cam

        factors = (zoom_factor(cam.shape, X.shape) for X in seed_inputs)
        cam = [zoom(cam, factor) for factor in factors]
        if standardize_cam:
            cam = [standardize(x) for x in cam]
        if len(self.model.inputs) == 1 and not isinstance(seed_input, list):
            cam = cam[0]
        return cam


ScoreCAM = Scorecam
