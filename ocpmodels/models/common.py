from typing import Callable, Optional, Union, Type, Any
from importlib import import_module

import torch
from torch import nn
from torch.nn.parameter import Parameter


def get_class_from_name(class_path: str) -> Type[Any]:
    """
    Load in a specified module, and retrieve a class within
    that module.

    The main use case for this function is to convert a class
    path into the actual class itself, in a way that doesn't
    allow arbitrary code to be executed by the user.

    Parameters
    ----------
    class_path : str
        String representation of the class path, such as `torch.nn.SiLU`

    Returns
    -------
    Type[Any]
        Loaded class reference
    """
    split_str = class_path.split(".")
    module_str = ".".join(split_str[:-1])
    class_str = split_str[-1]
    module = import_module(module_str)
    return getattr(module, class_str)


class OutputBlock(nn.Module):
    """
    Building block for output heads. Simple MLP stack with
    option to include residual connections.
    """

    def __init__(
        self,
        output_dim: int,
        activation: Optional[Union[nn.Module, Type[nn.Module], Callable, str]] = None,
        norm: Optional[Union[nn.Module, Type[nn.Module], Callable, str]] = None,
        input_dim: Optional[int] = None,
        lazy: bool = True,
        bias: bool = True,
        dropout: float = 0.0,
        residual: bool = True,
    ) -> None:
        """
        Initialize an `OutputBlock` MLP.

        This model uses `LazyLinear` layers to create uninitialized MLPs,
        which means no input dimensionality is needed to be specified.

        Parameters
        ----------
        output_dim : int
            Dimensionality of the output of this model.
        activation : Optional[Union[nn.Module, Type[nn.Module], Callable, str]], default None
            If None, uses `nn.Identity()` as a placeholder. This nonlinearity is applied
            before normalization.
        norm : Optional[Union[nn.Module, Type[nn.Module], Callable, str]], default None
            If None, uses `nn.Identity()` as a placeholder. This applies some normalization
            between hidden layers, after activation.
        dropout : float, default 0.
            Probability of dropout in hidden layers.
        residual : bool, default True
            Flag to specify whether residual connections are used between
            hidden layer.
        """
        super().__init__()
        if activation is None:
            activation = nn.Identity
        if isinstance(activation, str):
            activation = get_class_from_name(activation)
        if isinstance(activation, Type):
            activation = activation()
        if norm is None:
            norm = nn.Identity
        if isinstance(norm, str):
            norm = get_class_from_name(norm)
        if isinstance(norm, Type):
            norm = norm()
        self.residual = residual
        if lazy:
            linear = nn.LazyLinear(output_dim, bias=bias)
        else:
            if not lazy and not input_dim:
                raise ValueError(
                    f"Non-lazy model specified for 'OutputBlock', but no 'input_dim' was passed."
                )
            linear = nn.Linear(input_dim, output_dim, bias=bias)
        dropout = nn.Dropout(dropout)
        self.layers = nn.Sequential(linear, activation, norm, dropout)

    def forward(self, data: torch.Tensor) -> torch.Tensor:
        output = self.layers(data)
        if self.residual:
            assert output.shape == data.shape
            output = output + data
        return output

    @property
    def input_dim(self) -> int:
        """
        Return the expected input size of this ``OutputBlock``.

        Returns
        -------
        int
            ``nn.Linear`` weight matrix size
        """
        return self.layers[0].weight.size(-1)


class OutputHead(nn.Module):
    """
    A stack of output blocks, constituting an output head.

    Action of this stack is to transform a common embedding into
    actual outputs. The default settings will correspond to an
    MLP without any nonlinearities or normalizations.
    """

    def __init__(
        self,
        output_dim: int,
        hidden_dim: int,
        num_hidden: int = 1,
        activation: Optional[Union[nn.Module, Type[nn.Module], Callable, str]] = None,
        norm: Optional[Union[nn.Module, Type[nn.Module], Callable, str]] = None,
        act_last: Optional[Union[nn.Module, Type[nn.Module], Callable, str]] = None,
        input_dim: Optional[int] = None,
        lazy: bool = True,
        bias: bool = True,
        dropout: float = 0.0,
        residual: bool = True,
    ) -> None:
        """
        Initialize an `OutputHead` architecture.

        This model uses `LazyLinear` layers to create uninitialized MLPs,
        which means no input dimensionality is needed to be specified.

        Parameters
        ----------
        output_dim : int
            Dimensionality of the output of this model.
        hidden_dim : int
            Dimensionality of the hidden layers within this stack.
        num_hidden : int
            Number of hidden `OutputBlock`s to use.
        activation : Optional[Union[nn.Module, Type[nn.Module], Callable, str]], default None
            If None, uses `nn.Identity()` as a placeholder. This nonlinearity is applied
            before normalization for every hidden layer within the stack.
        norm : Optional[Union[nn.Module, Type[nn.Module], Callable, str]], default None
            If None, uses `nn.Identity()` as a placeholder. This applies some normalization
            between hidden layers, after activation.
        act_last : Optional[Union[nn.Module, Type[nn.Module], Callable, str]], default None
            If None, uses `nn.Identity()` as a a placeholder. This is an optional output
            layer activation function.
        dropout : float, default 0.
            Probability of dropout in hidden layers.
        residual : bool, default True
            Flag to specify whether residual connections are used between
            hidden layer.
        """
        super().__init__()
        blocks = [
            OutputBlock(
                hidden_dim,
                activation,
                norm,
                input_dim=input_dim,
                lazy=lazy,
                bias=bias,
                dropout=dropout,
                residual=False,
            ),
        ]
        # for everything in between
        blocks.extend(
            [
                OutputBlock(
                    hidden_dim,
                    activation,
                    norm,
                    input_dim=hidden_dim,
                    lazy=lazy,
                    bias=bias,
                    dropout=dropout,
                    residual=residual,
                )
                for _ in range(num_hidden)
            ]
        )
        # last layer does not use residual or normalization
        blocks.append(
            OutputBlock(
                output_dim,
                act_last,
                norm=None,
                input_dim=hidden_dim,
                lazy=lazy,
                bias=bias,
                residual=False,
            )
        )
        self.blocks = nn.Sequential(*blocks)

    def forward(self, embedding: torch.Tensor) -> torch.Tensor:
        expected_shape = self.blocks[0].input_dim
        assert (
            embedding.size(-1) == expected_shape
        ), f"Incoming encoder output dim ({embedding.size(-1)}) does not match the expected 'OutputBlock' dim ({expected_shape})"
        return self.blocks(embedding)


class RMSNorm(nn.Module):
    """
    Original code by https://github.com/bzhangGo/rmsnorm/blob/master/rmsnorm_torch.py
    """

    def __init__(self, input_dim: int, eps: float = 1e-8, bias: bool = False) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.eps = eps

        self.scale = Parameter(torch.ones(input_dim))
        self.bias = Parameter(torch.zeros(input_dim)) if bias else nn.Identity()
        self.has_bias = bias
        self.register_parameter("scale", self.scale)
        if bias:
            self.register_parameter("bias", self.bias)

    def forward(self, data: torch.Tensor) -> torch.Tensor:
        tensor_norm: torch.Tensor = torch.norm(data, p=2, dim=-1, keepdim=True)
        rms_values = torch.sqrt((tensor_norm * self.input_dim))
        # apply the RMSNorm to inputs
        norm_output = (data / (rms_values + self.eps)) * self.scale
        if self.has_bias:
            norm_output = norm_output + self.bias
        return norm_output


class PartialRMSNorm(RMSNorm):
    """
    Original code by https://github.com/bzhangGo/rmsnorm/blob/master/rmsnorm_torch.py

    This implements the partial RMS norm as a separate class to improve readibility
    and maintainability.
    """

    def __init__(
        self,
        input_dim: int,
        eps: float = 1e-8,
        partial: float = 0.5,
        bias: bool = False,
    ) -> None:
        super().__init__(input_dim, eps, bias)
        self.partial = partial

    @property
    def partial(self) -> float:
        return self._partial

    @partial.setter
    def partial(self, value: float) -> None:
        assert (
            0.0 < value < 1.0
        ), f"Partial value must be in the range [0,1]; value: {value}"
        self._partial = value

    @property
    def partial_length(self) -> int:
        return int(self.partial * self.input_dim)

    def forward(self, data: torch.Tensor) -> torch.Tensor:
        # split the input data along partial
        split_tensor, _ = torch.split(
            data, [self.partial_length, self.input_dim - self.partial_length], dim=-1
        )
        # compute norm based on the split portion
        tensor_norm: torch.Tensor = torch.norm(split_tensor, p=2, dim=1)
        rms_values = torch.sqrt((tensor_norm * self.partial_length))
        norm_output = (data / (rms_values + self.eps)) * self.scale
        if self.has_bias:
            norm_output = norm_output + self.bias
        return norm_output
