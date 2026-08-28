# fixtures/

Reference artefacts, for comparing against what you actually get.

**`example-response.json`** — one A2A reply from a surface with an Identity
element on *both* legs. Render it with:

```bash
python a2a_client.py --replay fixtures/example-response.json
```

That is what step 9 looks like when it works, and it is worth reading before
you configure anything, so you know what you are aiming at.

**Everything in it is synthetic.** The DIDs are `zEXAMPLE…` placeholders, the
UUIDs are zeroes, the code is `000000` and the `proofValue`s are strings, not
signatures. Nothing here was issued by a gateway and nothing here verifies. It
records the *shape* — which is all you need to recognise the real thing.

The two DIDs to look at are `credentialSubject.id`, which is the surface DID on
the response leg, and `workloadBinding.userIdentity.id`, which is the DID minted
on the inbound leg from your own message. They differ, and the second one is
you.
