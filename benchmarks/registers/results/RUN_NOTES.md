# Register consistency study: run notes

What happened during the run, as `PROTOCOL.md` requires.

- **Commits.** The protocol was committed at `a6ca17d` and the script at the next commit. `src/jaden` did not
  change during the study (`git log a6ca17d..HEAD -- src/jaden` is empty for the reported run).
- **Dry run.** Before the reported run, the script was tried with `--limit 600` (the first 600 records of each
  register) to check that every stage works; that output was discarded.
- **Each stage ran once**: audit (all 5,800,525 records), locate, second reader (jageocoder on the 194 conflicts
  whose address JADEN read as writing its municipality), sample, report.
- **A fix to the report after the run.** H4 is stated "in every register with coordinates". The first version of
  the report also counted the corporation register, which has no coordinates, as a register with 0 of 0 points
  agreeing, and so marked H4 as failed. The report was corrected to skip registers without coordinates; no
  number changed. With the correction H4 holds (99.5–99.8% in the three registers with coordinates).
- **Inspection.** The 294 sampled records were inspected one by one against the protocol's categories, using
  the address, the code's municipality, JADEN's reading, jageocoder's reading, the location signal, and for the
  municipality-less registers a re-reading of the address with the coded municipality put in front (whether the
  district is then found in the coded municipality). Every record's category and a one-line reason are in
  `inspection.csv`, so each judgment can be checked.
- **NTA conflicts.** All six have the same shape: the municipality column (which the code matches) followed by a
  street that names another municipality whose district exists only there. With no coordinates, nothing in the
  record says which field is right, so all six are U (cannot tell), as the protocol defines.

## What the inspection shows (analysis after the run)

- **When the address writes its municipality** (care offices), the audit's conflicts are mostly real: of 92
  inspected, 80 are codes that do not match the facility's location (C), 9 are addresses that name a
  neighbouring municipality while the code and location agree (T), and 3 are JADEN misreadings (R), each a
  district that shares a municipality's name (`丹波市町` in 天理市, `西宮市` in 行橋市, `八千代町` in 八幡西区).
- **When the address omits its municipality** (the MLIT welfare file), the audit's flags are almost all false:
  in all 150 inspected records the facility's point lies in the coded municipality. The address starts with a
  district that is also a municipality name (`北方町北方…` in 一宮市, `西宮市2-15-14` in 行橋市, `丸岡町…` in
  坂井市), or names a district that also exists elsewhere, and JADEN reads it as the other place. For such
  registers, `district_not_in_claimed` and `conflict` should not be taken as evidence against the code.
- **A systematic error**: 15 care-office conflicts carry 阿見町's code (084433) for offices whose address and
  location are elsewhere in Ibaraki (水戸市, 大洗町, 那珂市, 境町, ひたちなか市 and others).
