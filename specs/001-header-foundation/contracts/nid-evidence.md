# NID evidence contract

## Scope

The validator keeps three related facts separate:

1. Orbis nm demangling can render a readable C or C++ symbol spelling.
2. A PS4 dynamic symbol carries an opaque NID hash and, when present, encoded
   library/module table indexes.
3. A name map is external evidence that may associate the opaque NID with a
   readable name.

Demangling does not itself prove the NID association. Conversely, a community
map name does not establish PS4 ABI, loader, or behavioral equivalence.

The OpenOrbis ELF documentation describes the NID form as a hash followed by
library and module identifiers using the PS4 alphabet
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-. The
validator preserves the original encoded symbol and separately records the
decoded index values when the suffix is well formed. For dynamic SCE tags, the
upper table-index fields are compared with those decoded identifiers; the
lower string-table offsets are not treated as NID context indexes.

## Accepted inputs and provenance

The validate-implementation command accepts:

- JSON or whitespace-delimited text mappings as explicitly supplied
  source-bound mappings;
- the community-derived aerolib.csv mapping as a candidate mapping; and
- an optional JSON provenance manifest passed with
  --nid-database-provenance.

The community mapping is expected to be retained outside source control. Its
manifest should contain the following fields:

    {
      "authority": "community_reference",
      "source_url": "https://github.com/SocraticBliss/ps4_module_loader/blob/<commit>/aerolib.csv",
      "source_commit": "<full immutable commit>",
      "file_sha256": "<sha256 of the local mapping>",
      "nid_suffix_hex": "<16-byte NID suffix when known>"
    }

The report retains the local database path and SHA-256, manifest path and
SHA-256, authority, source URL, source commit, and NID suffix-derived checks.
The source URL and commit are provenance; they do not make a community source
official.

## Resolution states

NidBinding.status and NidBinding.resolution are independent from demangled
symbol text:

| Resolution | Meaning | Promotion |
| --- | --- | --- |
| opaque | No name was supplied or the NID is absent from the map | not observed |
| explicit_source_bound | A non-community mapping supplied the name | observed unless a hash/context conflict is found |
| community_candidate | A community name is available but hash, context, or pinned provenance is incomplete | partial; never target-object-equivalent |
| community_verified | Community name, NID hash, encoded library/module context, and pinned provenance all verify | observed for the NID dimension |
| conflicting | Hash, context, or mapping evidence disagrees | failed; never promoted |

The NID hash check uses SHA-1 over the mapped name followed by the supplied
16-byte suffix, reverses the first eight digest bytes, and encodes them using
the PS4 URL-safe base64 spelling described by the OpenOrbis reference. No
suffix means hash verification is not observed. Missing dynamic table context
or a malformed/mismatched suffix is not guessed and cannot promote a
community candidate.

The validation report schema is 4.1 because NidBinding now serializes
resolution, encoded indexes, hash status, and context status. Historical 4.0
reports remain valid historical evidence and are not rewritten.
