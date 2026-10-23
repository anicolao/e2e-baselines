# Prompts

Development prompts from Andrew Nicolao, recorded 2026-10-23. These entries cover the initial analysis, document drafts, revisions, and repository setup.

Result: initial commit on `main` in `anicolao/e2e` (direct bootstrap; no PR).

## 1

```text
Our goal is to design an e2e skill and tools framework that enables my programs to achieve the same level of e2e certainty they have today while offloading image storage (and possibly image generation) to github runners and github repos that are not directly the same repos as the repos that rely on those baselines. For starters, review ../food and ../games/quortextt to see how the E2E_GUIDE.md specifies the kinds of functionality I expected originally. Then look at ../pantheon for an example of how this has become a huge disk space problem, with that one repository requiring 100Gb or more of space as compared to quortextt's mere 1.5G. The solution I am thinking of is one where perhaps instead of doing a comparison of pixels, the e2e tests capture a snapshot and compare an md5sum to a recorded value for equality: since we hae 0-pixel tolerance, we only need the actual image to analyze it in case of failure. Meanwhile, a CAS of md5sums -> images can contain the actual images in a separate github repo, from which we can fetch just the images we need as we need them to do visual diffs. Other architectures are possible too. Consider alternatives and propose a design option; make no changes, just analyze for now.
```

## 2

```text
ok clearly byte-for-byte equivalence is a stronger guarantee than pixel equivalence, and easier to verify too. Let's build a new system that requires that, since anywhere we are currently doing pixel equivalence should be handled fine? We do not need to satisfy the requirements of all the existing repositories, I will not migrate them. But I do want a system that works for pantheon, so we can use it as a testbed: first of all, that would enable us to recover a lot of wasted disk and repo size, and secondly it's among my most modern projects and can form the baseline for future work and requirements. With those things in mind, let's write E2E_FRAMEWORK_PROPOSAL.md with a design for how this works in general for *new* projects, and an E2E_POC_PANTHEON.md that specifies how we'll test it on that example project.
```

## 3

```text
rewrite for brevity. Avoid references to other projects that aren't involved, schemes that are not chosen (like MD5), things that won't happen taht are already excluded by definitive statements of what will happen (e.g. that pixel similarity can't produce a matching result which is obvious since that won't be byte-for-byte identical). use more casual language, and always use fewer words where possible. Focus on what we will do, never on what we will not do unless necessary to express the alternative. Write a STYLE_GUIDE.md with writing rules so that we can remember how to write good documents later.
```

## 4

```text
can github release artifacts be linked from markdwon in the application repository so that the 'viewer' is just looking at the README.md for the e2e story?
```

## 5

```text
private repositories are out of scope. Remove all requirements relating to them. also look for opportunities to use plainer language: the brevity is good now, but for just one example, we write "Passing captures are discarded after recording their hashes and timings. Passing
verification needs only the application checkout and manifests; baseline image
downloads are zero." when we could write something like "Verifying a screenshot only requires validating the hashes using the manifest, so we don't need to download baselines or store successful comparisons." This alternative is easier to read, more direct, and captures the essential points of the original, right?
```

## 6

```text
OK this plan looks good. We need to record it in a github repo somewhere. The long term plan is for this to be part of https://github.com/machinapractica ... spend a moment to review what to do to set this up for eventual inclusion, then propose where we shoudl make the initial e2e repository.
```

## 7

```text
I think what we're doing replaces @machinapractica/testing
```

## 8

```text
ok
```

## 9

Recorded 2026-10-23 from Andrew Nicolao. Result: framework implementation and Pantheon POC commits on `main`; run evidence is linked from the POC report.

```text
OK let's proceed with the PoC and prove out the framework.
```
