export default {
  en: {
    explore: {
      reasons: {
        untested: "the model could not be tested on well-counted years",
        fill_error: "filling the gaps misses known totals by a wide margin",
        intervals_too_narrow: "its intervals miss known totals too often",
        mostly_filled: "most of a typical season is estimated, not counted",
        wide_intervals: "the yearly estimates are very uncertain",
        borrowed_profile: "its time of day is borrowed from similar species",
        totals: "the yearly totals are uncertain",
        smooth_band: "the trend's interval is very wide",
        passage_band: "the passage date is uncertain",
        beyond_counting: "much of its passage falls outside the counting season",
        tails_band: "the start and end of its passage are uncertain",
        few_birds: "too few birds a season to follow its timing",
      },
      picker: {
        groups: "Show groups",
        groupsHelp:
          "Birds not identified to species (e.g. harrier sp., Red/Black Kite), each read together with all the species it may include",
        groupOf: "group · {n}",
        label: "Search a species",
        searchAll: "{n} found among all species",
        none: "No species found",
        birdsTitle: "birds counted in a typical recent season",
        filter: {
          highlight: "Highlights",
          raptors: "Raptors",
          waterbirds: "Waterbirds & large birds",
          passerines: "Songbirds",
          other: "Pigeons, swifts & others",
          all: "All",
        },
        help: {
          highlight: "Common species with the most reliable data",
          raptors: "Eagles, kites, buzzards, harriers, falcons",
          waterbirds: "Storks, herons, cranes, cormorants, ducks, gulls, waders",
          passerines: "Finches, swallows, pipits, thrushes, crows…",
          other: "Pigeons, swifts, bee-eaters, woodpeckers…",
          all: "Every species counted often enough for a page",
        },
        sort: {
          taxonomic: "Taxonomic",
          common: "Most abundant",
        },
        story: {
          full: "counts and reliable model",
          caveat: "model, read with care",
          counts: "counts only",
        },
      },
    },
  },
};
