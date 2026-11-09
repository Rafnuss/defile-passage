/** Day of year (1-366) -> "12 Sep" in the given locale, in a non-leap year. */
export function doyLabel(doy, locale) {
  const d = new Date(Date.UTC(2001, 0, 1) + (Math.round(doy) - 1) * 86400000);
  return d.toLocaleDateString(locale, { day: "numeric", month: "short", timeZone: "UTC" });
}

// --- solar time -------------------------------------------------------------------------------
// The export gives hours of the day in local apparent solar time (hour 12 starts at the sun's
// transit over the Défilé, defile-passage `export.solar_shift`). The page shows clock time: the
// solar hour plus the day's shift, as there.

const SITE_LON = 5.914877; // defile-passage release.SITE

/** Offset of Europe/Paris from UTC (hours) at local noon on a date. */
function zoneOffset(date) {
  const noon = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), 11));
  const name = new Intl.DateTimeFormat("en-US", {
    timeZone: "Europe/Paris",
    timeZoneName: "shortOffset",
  })
    .formatToParts(noon)
    .find((p) => p.type === "timeZoneName").value; // "GMT+2"
  return Number(name.replace("GMT", "") || 0);
}

/**
 * Hours from solar time to clock time at the Défilé on a date (clock = solar + shift): the zone's
 * offset, less the longitude's and the equation of time (NOAA's series), as defile-passage
 * `export.solar_shift`.
 */
export function solarShift(date) {
  const start = Date.UTC(date.getUTCFullYear(), 0, 1);
  const g = ((2 * Math.PI) / 365) * Math.floor((date - start) / 86400000);
  const eot =
    229.18 *
    (0.000075 +
      0.001868 * Math.cos(g) -
      0.032077 * Math.sin(g) -
      0.014615 * Math.cos(2 * g) -
      0.040849 * Math.sin(2 * g));
  return zoneOffset(date) - SITE_LON / 15 - eot / 60;
}

/** A day of year as a UTC date in the given year. */
export const doyDate = (doy, year) =>
  new Date(Date.UTC(year, 0, 1) + (Math.round(doy) - 1) * 86400000);

/** Clock time "10:30" of a fractional hour, rounded to `step` minutes. */
export function clock(h, step = 1) {
  const m = Math.round((h * 60) / step) * step;
  return `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

// Same picker helpers as defileViz.
export const taxonName = (taxon, locale) =>
  (locale === "fr" && taxon.french_name) || taxon.english_name;
export const isGroup = (taxon) => taxon.taxon_rank === "spuh" || taxon.taxon_rank === "slash";
