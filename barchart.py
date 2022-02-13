import calendar
import csv
from fileinput import filename
import logging
from pathlib import Path
from sre_constants import IN_LOC_IGNORE
from typing import Collection, Optional

import ebird_interface


class Barchart:
    """
    A class for storing and manipulating data from eBird Bar Chart Data csv files.
    
    Stores all the data that can be extracted from an eBird Bar Chart file.
    """
    BC_FILE_SAMPLE_SIZE_ROW = 14
    BC_FILE_OBS_START_ROW = 16

    def __init__(self, filename: str, file_text: str) -> None:
        self._ingest_filename(filename)
        self._ingest_csv_data(file_text)
        self.name = ebird_interface.hotspot_name_from_loc_id(self.loc_id)

    def _ingest_filename(self, filename: str) -> None:
        """Populates instance variables with information from an eBird barchart file's filename."""
        parts = filename.split("_")
        self.loc_id: str = parts[1]
        self.start_year: int = int(parts[3])
        self.end_year: int = int(parts[4])
        self.start_month: int = int(parts[5])
        self.end_month: int = int(parts[6])
    
    def _ingest_csv_data(self, csv_data_string: str) -> None:
        """Populates instance variables with information from an eBird barchart file."""
        data_rows = [row for row in csv.reader(csv_data_string.splitlines(), dialect="excel-tab")]
        self.sample_sizes: list = [int(float(s)) for s in data_rows[self.BC_FILE_SAMPLE_SIZE_ROW][1:] if s]
        self.observations: dict = {}
        for row in data_rows[self.BC_FILE_OBS_START_ROW:]:
            if not row:
                continue
            sp_name = self.clean_sp_name(row[0])
            obs_list = [int(float(obs) * sample) for obs, sample in zip(row[1:], self.sample_sizes)]
            self.observations[sp_name] = obs_list
        self.species: set = set()
        self.other_taxa: set = set()
        for sp in self.observations:
            if self.is_good_species(sp):
                self.species.add(sp)
            else:
                self.other_taxa.add(sp)
    
    @classmethod
    def new_from_csv(cls, csv_path: Path) -> "Barchart":
        """Returns a Barchart object populated with data from an eBird CSV."""
        filename = csv_path.stem
        with open(csv_path, "r") as in_file:
            file_text = in_file.read()
        return Barchart(filename, file_text)
        
    @ staticmethod
    def clean_sp_name(sp_name: str) -> str:
        """Returns a species name stripped of html information, if present."""
        return sp_name.partition(" (<")[0]
    
    @staticmethod
    def is_good_species(sp_name: str) -> bool:
        """Returns True if the supplied species name contains substrings that indicate it is a sub-species level taxon."""
        flag_strings = (" sp.", " x ", "/", "Domestic", "hybrid")
        for flag in flag_strings:
            if flag.lower() in sp_name.lower():
                return False
        return True
    
    @property
    def species_observations(self) -> dict:
        return {sp: self.observations[sp] for sp in self.species}

    @property
    def other_taxa_observations(self) -> dict:
        return {ot: self.observations[ot] for ot in self.other_taxa}

    @staticmethod
    def _combined_average(samp_sizes: Collection, obs: Collection) -> float:
        if len(samp_sizes) != len(obs):
            raise ValueError(f"Sample Sizes and Observation data of different lengths supplied.")
            # ^^^ The lengths of the sample sizes and observation data should always
            #     be the same, or else the math will seem right, but be wrong.
        if sum(samp_sizes) == 0:
            return 0.0
        return round(sum(obs) / sum(samp_sizes), 5)

    def build_summary_dict(self, start: int = 0, end: int = 47, include_sub_species: bool = False) -> dict:
        """
        Returns a dictionary of observation data summarized to a single number per species.
        """
        summary = {}
        for sp, obs in self.observations.items():
            if not(sp in self.species or include_sub_species):
                continue
            av_obs = self._combined_average(self.sample_sizes[start: end], obs[start: end])
            if av_obs:
                summary[sp] = av_obs
        return summary

    def __repr__(self) -> str:
        return f"<Barchart for {self.name}>"


class Summarizer:
    
    def __init__(self, barcharts: list) -> None:
        pass

    def build_summary_dict(self, start: int = 0, end: int = 47, include_sub_species: bool = False) -> dict:
        pass



def summarize(bc_files: list) -> None:
    pass


def _collect_bc_files_from_folder(folder: Path) -> list:
    #TODO: "ebird_..._barchart.txt"
    pass


def test():
    test_bc_path = Path(__file__).parent / "data" / "testing" / "ebird_L109516__1900_2021_1_12_barchart.txt/"
    test_bc = Barchart.new_from_csv(test_bc_path)
    #print(test_bc.build_summary_dict(start=14, end=16))
    #print(len(test_bc.observations))
    #print(test_bc.other_taxa)


if __name__ == "__main__":
    test()