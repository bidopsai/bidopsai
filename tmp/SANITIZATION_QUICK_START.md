# Quick Start: Public Repo Sanitization

## TL;DR - What to Do

### ⚡ 5-Minute Action Plan

```bash
# 1. Make script executable
chmod +x scripts/sanitize-for-public.sh

# 2. Run sanitization (creates clean copy in /tmp)
./scripts/sanitize-for-public.sh

# 3. Review the result
cd /tmp/bidopsai-public
cat PUBLIC_REPO_NOTICE.md
cat agentcore/agent.py  # Should be stub

# 4. Create public GitHub repo
gh repo create bidopsai/bidopsai-hackathon --public --source=.

# 5. Push
git remote add origin git@github.com:bidopsai/bidopsai-hackathon.git
git push -u origin main

# 6. Submit to hackathon
# Use: https://github.com/bidopsai/bidopsai-hackathon
```

---

## 🎯 What Gets Removed vs. Kept

### 🔒 REMOVED (Your Secret Sauce)
- `agentcore/` implementation → **Replaced with stub**
- Proprietary business logic
- Real credentials
- Client-specific code
- Test data with real info

### ✅ KEPT (For Judges)
- Architecture diagrams ✅
- Infrastructure code (CDK) ✅
- UI/UX components ✅
- Documentation ✅
- GraphQL schema structure ✅
- Deployment guides ✅

**Result**: Judges can see your architecture and innovation, but can't steal your implementation.

---

## 📋 Pre-Flight Checklist

Before running the script, verify:

- [ ] You've committed all current work to main branch
- [ ] You have `gh` CLI installed (`brew install gh` or `apt install gh`)
- [ ] You're authenticated with GitHub (`gh auth login`)
- [ ] You have 1GB free space in `/tmp`

---

## 🔍 What the Script Does

1. **Clones** your repo to `/tmp/bidopsai-public`
2. **Deletes** sensitive directories:
   - `agentcore/*.py` (keeps Dockerfile, requirements.txt)
   - `.env*` files
   - `tmp/`, `.venv/`, `__pycache__/`
   - `docs/scratches/`
   - Test contracts and seed data

3. **Creates** stub files:
   - `agentcore/agent.py` - Documented stub showing architecture
   - `.env.example` - Generic configuration templates
   - `PUBLIC_REPO_NOTICE.md` - Explains what's redacted

4. **Sanitizes** docs:
   - Replaces AWS account ID in internal docs (keeps in public ones)
   - Leaves Cognito IDs (they're public auth endpoints anyway)

5. **Commits** changes with clear message

---

## 🚨 Manual Review (IMPORTANT!)

After running script, check these files:

```bash
cd /tmp/bidopsai-public

# 1. Agent should be stub
head -20 agentcore/agent.py
# Should say "HACKATHON SUBMISSION NOTICE" at top

# 2. No real .env files
ls -la **/.env*
# Should only see .env.example files

# 3. Search for secrets
grep -r "AKIA" .  # AWS access keys
grep -r "aws_secret_access_key" .
# Should find nothing

# 4. Check git log
git log -1 --stat
# Should show "sanitize for public hackathon submission"
```

---

## 🎬 What Happens After Push

Your public repo will have:

```
bidopsai-hackathon/
├── PUBLIC_REPO_NOTICE.md        ← Explains what's redacted
├── HACKATHON_SUBMISSION.md      ← Your full submission doc
├── README.md                    ← Project overview
├── agentcore/
│   ├── agent.py                 ← STUB with architecture docs
│   ├── README.md                ← Explains what's missing
│   ├── Dockerfile               ← Real (for judging)
│   └── requirements.txt         ← Real dependencies
├── apps/web/                    ← Full UI/UX (impressive!)
├── services/core-api/           ← Schema structure only
├── infra/                       ← CDK code (generic config)
└── docs/                        ← All architecture docs
```

Judges can:
- ✅ See your architecture and design
- ✅ Understand your multi-agent approach
- ✅ Evaluate your AWS service usage
- ✅ Review your UI/UX quality
- ✅ Read your documentation

Judges cannot:
- ❌ Copy your proprietary agent logic
- ❌ Steal your business algorithms
- ❌ Access your production system
- ❌ See client-specific implementations

---

## 💡 Pro Tips

### If You Want to Keep More
Edit `scripts/sanitize-for-public.sh` and comment out deletions:
```bash
# rm -rf agentcore/*.py  # Keep this to show implementation
```

### If You Want to Remove More
Add to the `rm -rf` section:
```bash
rm -rf \
  apps/web/src/lib/api/ \     # Remove API integration code
  services/core-api/src/resolvers/ \  # Remove all resolvers
```

### Custom Output Location
```bash
./scripts/sanitize-for-public.sh /path/to/custom/location
```

---

## 🆘 Troubleshooting

**Q: Script fails with "not a git repository"**  
A: Run from repo root: `cd /home/vekysilkova/projects/bidopsai`

**Q: "gh command not found"**  
A: Install GitHub CLI: `sudo apt install gh` or `brew install gh`

**Q: Want to undo?**  
A: Just delete `/tmp/bidopsai-public` and run again. Your original repo is untouched.

**Q: Can I edit after sanitization?**  
A: Yes! The sanitized repo is just a copy. Edit `/tmp/bidopsai-public` before pushing.

**Q: Should I delete the original repo?**  
A: NO! Keep your private repo. The public one is for hackathon only.

---

## 📊 What Organizers Said

> "We can upload the code to public repo by masking or removing the part we don't want to share. It's not mandatory that the code should be working, but just enough to showcase our work."

**Translation:**
- ✅ Show architecture and approach
- ✅ Demonstrate innovation
- ✅ Prove you built it
- ❌ Don't need working system
- ❌ Don't expose secret sauce

**Your sanitized repo does exactly this!**

---

## ⏱️ Time Estimate

- **Script execution**: 2 minutes
- **Manual review**: 15 minutes
- **GitHub push**: 2 minutes
- **Documentation cleanup** (if needed): 30 minutes

**Total**: ~30-50 minutes from start to public repo

---

## 🎯 Final Step: Hackathon Submission

Once public repo is ready:

1. **Verify URL**: https://github.com/bidopsai/bidopsai-hackathon
2. **Check README**: Should have architecture overview
3. **Test clone**: `git clone https://github.com/bidopsai/bidopsai-hackathon` (should work publicly)
4. **Submit to Devpost** with:
   - Public repo URL
   - Demo video (if you have one)
   - `HACKATHON_SUBMISSION.md` as description

---

**Ready? Run the script!**

```bash
chmod +x scripts/sanitize-for-public.sh
./scripts/sanitize-for-public.sh
```

Good luck! 🚀
