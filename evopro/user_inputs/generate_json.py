import json
import re
import sys
from inputs import FileArgumentParser
import math

def generate_json(pdbfile, mut_res, opf, default, symmetric_res):
    sys.path.append("/proj/kuhl_lab/evopro/")
    from evopro.utils.pdb_parser import get_coordinates_pdb
    from evopro.utils.aa_utils import three_to_one

    chains, residues, resindices = get_coordinates_pdb(pdbfile, fil=True)

    pdbids = {}
    chain_seqs = {}

    for chain in chains:
        chain_seqs[chain]=[]

    res_index_chain = 1
    chain_test = chains[0]
    for residue in residues:
        num_id = int(residue.split("_")[-1])
        chain = residue.split("_")[0]
        if chain != chain_test:
            res_index_chain = 1
            chain_test = chain
        pdbid = chain+str(num_id)
        pdbids[pdbid] = (residue, chain, res_index_chain)
        aa = three_to_one(residue.split("_")[1])
        chain_seqs[chain].append(aa)
        res_index_chain += 1

    for chain in chains:
        chain_seqs[chain] = "".join([x for x in chain_seqs[chain] if x is not None])

    mutable = []
    for resind in mut_res:
        if resind in pdbids:
            mutable.append({"chain":pdbids[resind][1], "resid": pdbids[resind][2], "WTAA": three_to_one(pdbids[resind][0].split("_")[1]), "MutTo": default})

    symmetric = []
    for symmetry in symmetric_res:
        values = list(symmetry.values())

        for tied_pos in zip(*values):
            skip_tie = False
            sym_res = []
            for pos in tied_pos:
                res_id = pos[0] + str(pos[1])
                if pdbids[res_id][0] == 'X':
                    skip_tie = True
                    break
                else:
                    sym_res.append( pdbids[res_id][1] + str(pdbids[res_id][2]) )

            if not skip_tie:
                symmetric.append(sym_res)

    dictionary = {"sequence" : chain_seqs, "designable": mutable, "symmetric": symmetric}
    jsonobj = json.dumps(dictionary, indent = 4)

    with open(opf, "w") as outfile:
        outfile.write(jsonobj)
    
def getPDBParser() -> FileArgumentParser:
    """Gets an FileArgumentParser with necessary arguments to run generate_json"""

    parser = FileArgumentParser(description='Script that can take a PDB and PDB residue numbers'
                                ' and convert to json file format for input to FDD', 
                                fromfile_prefix_chars='@')

    parser.add_argument('--pdb',
                        default='',
                        type=str,
                        help='Path to and name of PDB file')
    parser.add_argument('--mut_res',
                        default='',
                        type=str,
                        help='PDB chain and residue numbers to mutate, separated by commas')
    parser.add_argument('--default_mutres_setting',
                        default='all',
                        type=str,
                        help='Default setting for residues to mutate. Individual ones can be changed manually. Default is all')
    parser.add_argument('--output',
                        default='',
                        type=str,
                        help='path and name of output json file')
    parser.add_argument('--symmetric_res',
                        default='',
                        type=str,
                        help='PDB chain and residue numbers to force symmetry separated by a colon')
    return parser

def parse_mutres_input(mutresstring):
    mutres_temp = mutresstring.strip().split(",")
    mutres_temp = [x for x in mutres_temp if x]
    mutres = []
    for elem in mutres_temp:
        if "-" not in elem:
            mutres.append(elem)
        else:
            start, finish = elem.split("-")
            chain = re.split('(\d+)', start)[0]
            s = int(re.split('(\d+)', start)[1]) 
            f = int(re.split('(\d+)', finish)[1]) 
            for i in range(s, f+1):
                mutres.append(chain + str(i))
    return mutres

def _check_res_validity(res_item):
    split_item = [item for item in re.split('(\d+)', res_item) if item]

    if len(split_item) != 2:
        raise ValueError(f'Unable to parse residue: {res_item}.')
    return (split_item[0], int(split_item[1]))

def _check_range_validity(range_item):
    split_range = range_item.split('-')
    if len(split_range) != 2:
        raise ValueError(f'Unable to parse residue range: {range_item}')

    start_item, finish_item = split_range[0], split_range[1]

    s_chain, s_idx = _check_res_validity(start_item)
    f_chain, f_idx = _check_res_validity(finish_item)
    if s_chain != f_chain:
        raise ValueError(f'Residue ranges cannot span multiple chains: {range_item}')
    if s_idx >= f_idx:
        raise ValueError(f'Residue range starting index must be smaller than the ending index: '
                             f'{range_item}')

    res_range = []
    for i in range(s_idx, f_idx + 1):
        res_range.append( (s_chain, i) )

    return res_range

def _check_symmetry_validity(symmetric_item):
    split_item = symmetric_item.split(':')

    symmetry_dict = {}
    for subitem in split_item:
        if '-' in subitem:
            res_range = _check_range_validity(subitem)
            symmetry_dict[subitem] = res_range
        else:
            res_ch, res_idx = _check_res_validity(subitem)
            symmetry_dict[subitem] = [(res_ch, res_idx)]

    item_lens = [len(symmetry_dict[key]) for key in symmetry_dict]
    if math.floor(sum([l == item_lens[0] for l in item_lens])/len(item_lens)) != 1:
        raise ValueError(f'Tied residues and residue ranges must be of the same '
                             f'size for forcing symmetry: {symmetric_item}')

    return symmetry_dict

def parse_symmetric_res(symmetric_str):

    symmetric_str = [s for s in symmetric_str.strip().split(",") if s]

    symmetric_res = []
    for item in symmetric_str:
        if ":" not in item:
            raise ValueError(f'No colon detected in symmetric res: {item}.')

        symmetry_dict = _check_symmetry_validity(item)
        symmetric_res.append(symmetry_dict)

    return symmetric_res
    

if __name__=="__main__":
    parser = getPDBParser()
    args = parser.parse_args(sys.argv[1:])
    mutres = parse_mutres_input(args.mut_res)
    symres = parse_symmetric_res(args.symmetric_res)
    generate_json(args.pdb, mutres, args.output, args.default_mutres_setting, symres)
