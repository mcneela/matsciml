import pytest

from ocpmodels.datasets.utils import concatenate_keys
from ocpmodels.datasets.materials_project import (
    materialsproject_devset,
    MaterialsProjectDataset,
)
from ocpmodels.datasets import is2re_devset, IS2REDataset
from ocpmodels.datasets.transforms import (
    PointCloudToGraphTransform,
    OCPGraphToPointCloudTransform,
)


def test_collate_mp_pc():
    # uses point clouds
    dset = MaterialsProjectDataset(materialsproject_devset)
    samples = [dset.__getitem__(i) for i in range(4)]
    batch = concatenate_keys(samples, pad_keys=["pos", "pc_features", "atomic_numbers"])
    pos = batch["pos"]
    assert pos.ndim == 4
    # batch size of 4 and 3 dimensions for xyz
    assert pos.size(-1) == 3
    assert pos.size(0) == 4
    assert "mask" in batch


def test_collate_mp_dgl():
    # uses graphs instead
    dset = MaterialsProjectDataset(
        materialsproject_devset, transforms=[PointCloudToGraphTransform("dgl")]
    )
    samples = [dset.__getitem__(i) for i in range(4)]
    # no keys needed to be padded
    batch = concatenate_keys(samples)
    assert "graph" in batch
    graph = batch["graph"]
    assert graph.batch_size == 4
    assert all([key in batch for key in ["targets", "target_types"]])


def test_collate_is2re_dgl():
    dset = IS2REDataset(is2re_devset)
    samples = [dset.__getitem__(i) for i in range(4)]
    # no keys needed to be padded
    batch = concatenate_keys(samples)
    assert "graph" in batch
    graph = batch["graph"]
    assert graph.batch_size == 4
    assert all([key in batch for key in ["targets", "target_types"]])


def test_collate_is2re_pc():
    dset = IS2REDataset(is2re_devset, transforms=[OCPGraphToPointCloudTransform("dgl")])
    samples = [dset.__getitem__(i) for i in range(4)]
    # no keys needed to be padded
    batch = concatenate_keys(samples, pad_keys=["pos", "pc_features"])
    assert all(
        [
            key in batch
            for key in ["pos", "pc_features", "mask", "targets", "target_types"]
        ]
    )
