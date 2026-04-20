#!/usr/bin/env python3

import sys
import os
from Bio import SeqIO

if len(sys.argv) != 2:
    print("Usage: python 3_ir_checking.py input.gb")
    sys.exit(1)

gb_file = sys.argv[1]
base = os.path.splitext(gb_file)[0]

log_file = base + "_check.log"

EXCLUDE_FROM_IR = {"rps12", "ycf68"}

with open(log_file, "w") as log:

    log.write("IR STRUCTURE CHECK (Overlap Mode)\n")
    log.write("=================================\n\n")

    if not os.path.isfile(gb_file):
        log.write("ERROR: Input file not found.\n")
        sys.exit(1)

    record = SeqIO.read(gb_file, "genbank")

    # --------------------------------------------------
    # Detect IR regions
    # --------------------------------------------------

    IR_features = []

    for f in record.features:
        if f.type == "repeat_region":
            note = f.qualifiers.get("note", [])
            if any("inverted repeat" in x.lower() for x in note):
                IR_features.append(f)

    if len(IR_features) != 2:
        log.write("ERROR: Could not detect exactly two IR regions.\n")
        sys.exit(1)

    IRA = IR_features[0].location
    IRB = IR_features[1].location

    # --------------------------------------------------
    # Length calculation (join-safe)
    # --------------------------------------------------

    def location_length(loc):
        parts = getattr(loc, "parts", [loc])
        return sum(int(p.end) - int(p.start) for p in parts)

    IRA_length = location_length(IRA)
    IRB_length = location_length(IRB)

    log.write("Region\tLength\n")
    log.write("----------------------\n")
    log.write(f"IRA\t{IRA_length}\n")
    log.write(f"IRB\t{IRB_length}\n\n")

    # --------------------------------------------------
    # GLOBAL IR length comparison (ONLY EXIT CONDITION)
    # --------------------------------------------------

    if IRA_length == IRB_length:
        log.write("✔ Global IR lengths identical.\n\n")
    else:
        log.write("❌ Global IR length mismatch detected.\n")
        log.write(f"Difference: {abs(IRA_length - IRB_length)} bp\n\n")

    # --------------------------------------------------
    # Gene fragment length inside IR (report only)
    # --------------------------------------------------

    def overlap_length(region, feature):

        total = 0

        region_parts = getattr(region, "parts", [region])
        feature_parts = getattr(feature.location, "parts", [feature.location])

        for fpart in feature_parts:
            fstart = int(fpart.start)
            fend   = int(fpart.end)

            for rpart in region_parts:
                rstart = int(rpart.start)
                rend   = int(rpart.end)

                start = max(fstart, rstart)
                end   = min(fend, rend)

                if start < end:
                    total += (end - start)

        return total


    def gene_lengths_in_ir(region):

        gene_lengths = {}

        for f in record.features:

            if f.type != "gene":
                continue

            name = f.qualifiers.get("gene", [None])[0]
            if not name or name in EXCLUDE_FROM_IR:
                continue

            olap = overlap_length(region, f)

            if olap > 0:
                gene_lengths[name] = gene_lengths.get(name, 0) + olap

        return gene_lengths


    IRA_lengths = gene_lengths_in_ir(IRA)
    IRB_lengths = gene_lengths_in_ir(IRB)

    all_genes = sorted(set(IRA_lengths.keys()) | set(IRB_lengths.keys()))

    mismatch_genes = []

    for gene in all_genes:

        len_A = IRA_lengths.get(gene, 0)
        len_B = IRB_lengths.get(gene, 0)

        if len_A != len_B:
            mismatch_genes.append((gene, len_A, len_B))

    # --------------------------------------------------
    # Report gene-level differences (NO EXIT)
    # --------------------------------------------------

    if not mismatch_genes:
        log.write("✔ Gene fragment lengths identical between IRA and IRB.\n\n")
    else:
        log.write("⚠ Gene fragment length differences detected:\n\n")
        log.write("Gene\tIRA_bp\tIRB_bp\n")
        log.write("--------------------------------\n")

        for gene, len_A, len_B in mismatch_genes:
            log.write(f"{gene}\t{len_A}\t{len_B}\n")

        log.write("\n")

# --------------------------------------------------
# PRINT LOG TO SHELL
# --------------------------------------------------

with open(log_file, "r") as log:
    print(log.read())

# exit only if global IR length mismatch
if IRA_length != IRB_length:
    sys.exit(1)
