from matsciml.datasets.carolina_db import CMDRequest, CMDataset

# Download an example material
req = CMDRequest(material_ids=[339])
req.download_data() # this downloads the .cif file
data = req.process_data()

dataset = CMDataset(lmdb_root_path="./matsciml/datasets/carolina_db/devset")

# get a random sample from the dataset
sample = dataset.sample(1)[0]
atom_numbers = sample['atomic_numbers']
energy = sample['energy']
symmetry = sample['symmetry']
lattice_params = sample['lattice_params']
coords = sample['pos']
