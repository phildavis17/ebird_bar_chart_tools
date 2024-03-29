import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Collection, Optional, List

from app import ebird_interface


# Utility Functions



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
        logging.info("Barchart created for %s" % self.name)

    def _ingest_filename(self, filename: str) -> None:
        """Populates instance variables with information from an eBird barchart file's filename."""
        parts = filename.split("_")
        self.loc_id: str = parts[1]
        self.start_year: int = int(parts[3])
        self.end_year: int = int(parts[4])
        self.start_month: int = int(parts[5])
        self.end_month: int = int(parts[6])

    @staticmethod
    def _get_blank_row() -> List[int]:
        """Returns a list of 48 zeros. Used as the default for the observation defaultdict"""
        return [0] * 48

    def _ingest_csv_data(self, csv_data_string: str) -> None:
        """Populates instance variables with information from an eBird barchart file."""
        data_rows = [row for row in csv.reader(csv_data_string.splitlines(), dialect="excel-tab")]
        self.sample_sizes: list = [int(float(s)) for s in data_rows[self.BC_FILE_SAMPLE_SIZE_ROW][1:] if s]
        self.observations: defaultdict = defaultdict(self._get_blank_row)
        for row in data_rows[self.BC_FILE_OBS_START_ROW:]:
            if not row:
                continue
            sp_name = self.clean_sp_name(row[0])
            obs_list = [round(float(obs) * sample) for obs, sample in zip(row[1:], self.sample_sizes)]
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
            # ^^^ If the lenghts of the sample sizes and obsevations are not the same,
            #     this method will produce an answer without complaint, but the information
            #     will be incorrect. This error prevents that.
        if sum(samp_sizes) == 0:
            return 0.0
        return round(sum(obs) / sum(samp_sizes), 5)

    def build_summary_dict(self, period_list: List[int], include_sub_species: bool = False) -> dict:
        """
        Returns a dictionary of observation data summarized to a single number per species.
        """
        summary = {}
        for sp, obs in self.observations.items():
            if not(sp in self.species or include_sub_species):
                continue
            samps = [self.sample_sizes[i] for i in period_list]
            obs_data = [obs[i] for i in period_list]
            av_obs = self._combined_average(samps, obs_data)
            if av_obs:
                summary[sp] = av_obs
        return summary

    @staticmethod
    def _build_period_range(start: int, end: int):
        if end < start:
            end += 48
        return [i % 48 for i in range(start, end + 1)]

    def __repr__(self) -> str:
        return f"<Barchart for {self.name}>"


class Summarizer:
    def __init__(self, barcharts: List["Barchart"], name: Optional[str] = None) -> None:
        self.name = name
        self.loc_ids = tuple(sorted([bc.loc_id for bc in barcharts]))
        self.hotspot_names = {bc.loc_id: bc.name for bc in barcharts}
        self.active_hotspots = set(self.loc_ids)
        self.total_sample_sizes = {bc.loc_id: bc.sample_sizes for bc in barcharts}
        self.total_obs_data = {bc.loc_id: bc.observations for bc in barcharts}
        self.total_species = set().union(*[bc.species for bc in barcharts])
        self.total_other_taxa = set().union(*[bc.other_taxa for bc in barcharts])

    @staticmethod
    def _combined_average(samp_sizes: Collection, obs: Collection) -> float:
        if len(samp_sizes) != len(obs):
            raise ValueError(f"Sample Sizes and Observation data of different lengths supplied.")
            # ^^^ If the lenghts of the sample sizes and obsevations are not the same,
            #     this method will produce an answer without complaint, but the information
            #     will be incorrect. This error prevents that.
        if sum(samp_sizes) == 0:
            return 0.0
        return round(sum(obs) / sum(samp_sizes), 5)

    def build_summary_dict(self, period_list: List[int], include_sub_species: bool = False) -> dict:
        """
        Returns a dictionary of observation data summarized to a single number per species.
        """
        summary_dict = {}
        for hs, obs_dict in self.total_obs_data.items():
            if hs not in self.active_hotspots:
                continue
            hs_summary = defaultdict(float)
            samples = [self.total_sample_sizes[hs][p] for p in period_list]
            for sp, obs_list in obs_dict.items():
                obs = [obs_list[p] for p in period_list]
                hs_summary[sp] = self._combined_average(samples, obs)
            summary_dict[hs] = hs_summary
        return summary_dict

    @staticmethod
    def _build_period_range(start: int, end: int):
        """Takes a start and end period, and creates a list of integers included in that range. Range includes bounds."""
        if end < start:
            end += 48
        return [i % 48 for i in range(start, end + 1)]

    @property
    def active_species(self) -> set:
        return {sp for hs in self.active_hotspots for sp in self.total_obs_data[hs] if sp in self.total_species}

    @property
    def active_other_taxa(self) -> set:
        return {sp for hs in self.active_hotspots for sp in self.total_obs_data[hs] if sp in self.total_other_taxa}

    def set_hotspot_inactive(self, loc_id: str) -> None:
        """Removes the supplied loc_id from the list of active hotspots."""
        if loc_id not in self.loc_ids:
            raise ValueError(f"Unrecognized hotspot loc_id: {loc_id}")
        self.active_hotspots.discard(loc_id)

    def set_hotspot_active(self, loc_id: str) -> None:
        """Adds the supplied loc_id from the list of active hotspots."""
        if loc_id not in self.loc_ids:
            raise ValueError(f"Unrecognized hotspot loc_id: {loc_id}")
        self.active_hotspots.add(loc_id)

    def summarize_period_total(self, periods: List[int], include_sub_species: bool = False) -> dict:
        """Returns a dict of observation data reduced to a single number per species for each hotspot."""
        sample_sizes = {}
        observations = {}
        for hs, obs_dict in self.total_obs_data.items():
            sample_sizes[hs] = sum([self.total_sample_sizes[hs][period] for period in periods])
            observations[hs] = sum([self.total_obs_data[hs][period] for period in periods])
        return {"samples": sample_sizes, "observations": observations}

    def _summarize_samples(self, periods: List[int]) -> dict:
        """Returns a dict of cumulative sample sizes for each hotspot for the specified periods."""
        return {hs: sum([samps[p] for p in periods]) for hs, samps in self.total_sample_sizes.items()}

    def _summarize_observations(self, periods: List[int]) -> dict:
        """Returns a dict of cumulative observations for each taxa for each hotspot for the specified periods."""
        summary_obs = {}
        for hs, obs_dict in self.total_obs_data.items():
            summary_obs[hs] = {sp: sum([obs[p] for p in periods]) for sp, obs in obs_dict.items()}
        return summary_obs

    @staticmethod
    def _overall_odds(odds_list: list) -> float:
        """Given a list of probabilities, returns the odds that at least one of them will succeed."""
        if not odds_list:
            raise ValueError("No odds values in list.")
        inverse_overall = 1
        for odds in odds_list:
            if not 0 <= odds <= 1:
                raise ValueError(f"Improper probablility: {odds}")
            inverse_overall *= 1 - odds
        return round(1 - inverse_overall, 5)

    def find_current_specialties(self, include_sub_species: bool = False) -> dict:
        pass

    def __len__(self):
        return len(self.loc_ids)


    ###### WHAT THE HELL IS THIS THING DOING ######
    # it needs to report:
    # -
    # -


def test():
    test_bc_path = Path(__file__).parent / "data" / "testing" / "ebird_L109516__1900_2021_1_12_barchart.txt/"
    test_bc = Barchart.new_from_csv(test_bc_path)



if __name__ == "__main__":
    test()
