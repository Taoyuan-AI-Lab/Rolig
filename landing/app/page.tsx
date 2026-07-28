"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";

const githubUrl = "https://github.com/Taoyuan-AI-Lab/Rolig";
const approvedFeedUrl = "/api/approved-feed";

type ApprovedMeme = {
  id: string;
  url: string;
  type: "image" | "video";
  tags: string[];
  summary: string;
  likeCount?: number;
  viewCount?: number;
};

const memeEras = [
  {
    years: "2016—2017",
    title: "Absurdity rises",
    className: "era-yellow",
    memes: [
      "Harambe", "Roll Safe", "Distracted Boyfriend", "Arthur's Fist",
      "Evil Kermit", "Mocking SpongeBob", "Blinking White Guy",
      "We Are Number One", "Shooting Stars", "Salt Bae",
      "Expanding Brain", "Cash Me Outside", "Pennywise in the Sewer",
      "Man's Not Hot", "Right In Front of My Salad?", "Dat Boi", "PPAP",
      "The Floor Is Lava", "First of All", "Cold One with the Boys",
    ],
  },
  {
    years: "2018—2019",
    title: "The pre-TikTok cut",
    className: "era-blue",
    memes: [
      "Ugandan Knuckles", "Is This a Pigeon?", "Surprised Pikachu",
      "Moth Memes", "Change My Mind", "Bowsette",
      "Surgery on a Grape", "Young Thug & Lil Durk", "Woman Yelling at Cat",
      "American Chopper Argument", "Baby Yoda", "Here We Go Again",
      "Me and the Boys", "Gonna Tell My Kids", "Storm Area 51",
      "Joker Dancing on Stairs", "Vibe Check", "Flex Tape",
      "Pro Gamer Move", "Boys vs Girls",
    ],
  },
  {
    years: "2020—2021",
    title: "Quarantine chaos",
    className: "era-coral",
    memes: [
      "Coffin Dance", "Nature is Healing", "Among Us",
      "Bernie in Mittens", "Anakin & Padmé", "Two Guys on a Bus",
      "Genshin Start!", "Trade Offer", "Cat Jam", "Always Has Been",
      "Line Without a Hook", "DaBaby Convertible", "Think, Mark!",
      "Sea Shanty TikTok", "Disaster Girl Sale", "Gorilla Glue Girl",
      "Kim K Met Gala", "Agatha Winking", "Squid Game Dalgona",
      "Bones or No Bones",
    ],
  },
  {
    years: "2022—2023",
    title: "Short-form supremacy",
    className: "era-white",
    memes: [
      "Will Smith Slap", "Skibidi Toilet", "Grimace Shake", "Corn Kid",
      "Smurf Cat", "Kevin James Smirk", "Pedro Laughing then Crying",
      "Let Me Do It For You", "The Rock Eyebrow", "GigaChad",
      "Gentleminions", "Chipi Chipi Chapa Chapa", "Bombastic Side Eye",
      "One Two Buckle My Shoe", "Barbenheimer", "Girl Dinner",
      "Canon Event", "Roman Empire", "Attentat", "Live Target Reaction",
    ],
  },
  {
    years: "2024—2026",
    title: "Brainrot & reset",
    className: "era-mix",
    memes: [
      "Chill Guy", "Demure & Mindful", "Hawk Tuah", "Gnome vs Knight",
      "Man in Finance", "Pedro Raccoon", "English or Spanish?",
      "We Are Not the Same", "Brainrot Language", "Familiar With Your Game",
      "The Great Meme Reset", "Dancing Rat", "AI Generative Chaos",
      "Y2K Corporate Core", "Neanderthal Reaction",
      "Infinite Scroll Paralysis", "Micro-Trend Fatigue",
      "Uncanny Valley Influencer", "Low-Poly Animals",
      "Retro-Futurism Nostalgia",
    ],
  },
] as const;

const feedItems = [
  {
    id: "deadline",
    kicker: "POV: you opened one tiny PR",
    caption: "The CI pipeline at 4:59 PM",
    creator: "@merge_conflict",
    likes: "12.8K",
    className: "meme-deadline",
    art: (
      <div className="deadline-art" aria-hidden="true">
        <div className="deadline-sun" />
        <div className="deadline-window" />
        <div className="deadline-desk" />
        <div className="deadline-laptop">99+</div>
        <div className="deadline-person">😵‍💫</div>
      </div>
    ),
  },
  {
    id: "cat",
    kicker: "Me acting natural",
    caption: "When someone says “quick icebreaker”",
    creator: "@quietly_online",
    likes: "8.4K",
    className: "meme-cat",
    art: (
      <div className="cat-art" aria-hidden="true">
        <span className="plant">🌿</span>
        <span className="cat">🐈</span>
        <span className="eyes">👀</span>
      </div>
    ),
  },
  {
    id: "weekend",
    kicker: "Saturday has entered the chat",
    caption: "Mood restored. No notes.",
    creator: "@weekend_loading",
    likes: "21.3K",
    className: "meme-weekend",
    art: (
      <div className="weekend-art" aria-hidden="true">
        <span>🕺</span>
        <i />
        <b>✨</b>
      </div>
    ),
  },
];

function ArrowIcon() {
  return <span aria-hidden="true">↗</span>;
}

function archiveOrder(items: ApprovedMeme[]) {
  return [...items].sort((a, b) => {
    const aMatch = new URL(a.url).pathname.match(/\/(\d{3})-/);
    const bMatch = new URL(b.url).pathname.match(/\/(\d{3})-/);
    const aOrder = aMatch ? Number(aMatch[1]) : 1000;
    const bOrder = bMatch ? Number(bMatch[1]) : 1000;
    return aOrder - bOrder;
  });
}

function MemoryMedia({
  item,
  paused,
  onError,
}: {
  item: ApprovedMeme;
  paused: boolean;
  onError: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!videoRef.current) return;
    if (paused) {
      videoRef.current.pause();
    } else {
      void videoRef.current.play().catch(() => undefined);
    }
  }, [item.id, paused]);

  if (item.type === "video") {
    return (
      <video
        ref={videoRef}
        className="memory-media"
        src={item.url}
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        onError={onError}
      />
    );
  }

  return (
    // The approved feed returns complete public R2 URLs at runtime.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="memory-media memory-image"
      src={item.url}
      alt={item.summary}
      onError={onError}
    />
  );
}

function CinematicIntro() {
  const [items, setItems] = useState<ApprovedMeme[]>([]);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [feedError, setFeedError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let retryTimer: number | undefined;

    const loadArchive = () => {
      void fetch(approvedFeedUrl, { signal: controller.signal })
        .then((response) => {
          if (!response.ok) throw new Error(`Feed request failed: ${response.status}`);
          return response.json() as Promise<{ items: ApprovedMeme[] }>;
        })
        .then((feed) => {
          if (feed.items.length === 0) throw new Error("Approved feed is empty");
          setItems(archiveOrder(feed.items));
          setFeedError(false);
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setFeedError(true);
          retryTimer = window.setTimeout(loadArchive, 6000);
        });
    };

    loadArchive();

    return () => {
      controller.abort();
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, []);

  useEffect(() => {
    if (paused || items.length === 0) return;
    const timer = window.setInterval(
      () => setIndex((value) => (value + 1) % items.length),
      2400,
    );
    return () => window.clearInterval(timer);
  }, [items.length, paused]);

  const current = items[index];
  const next = items.length > 0 ? items[(index + 1) % items.length] : undefined;
  const progress = items.length > 0 ? ((index + 1) / items.length) * 100 : 0;
  const era =
    index < 5 ? "2016—2017" :
    index < 11 ? "2018—2019" :
    index < 14 ? "2020—2021" :
    index < 17 ? "2022—2024" :
    "ROLIG NOW";

  const advance = () => {
    if (items.length > 0) setIndex((value) => (value + 1) % items.length);
  };

  return (
    <section
      className={`cinematic-intro memory-intro ${paused ? "intro-paused" : ""}`}
      id="top"
      aria-labelledby="cinematic-title"
    >
      <div className="memory-stage" aria-live="off">
        {current ? (
          <MemoryMedia
            key={current.id}
            item={current}
            paused={paused}
            onError={advance}
          />
        ) : (
          <div className="memory-loading">
            <Image src="/rolig-logo.png" alt="" width={96} height={96} priority />
            <span>{feedError ? "The archive is waking up…" : "Loading the Rolig archive…"}</span>
          </div>
        )}
      </div>

      {next ? (
        <div className="memory-preload" aria-hidden="true">
          {next.type === "image" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={next.url} alt="" />
          ) : (
            <video src={next.url} muted preload="metadata" />
          )}
        </div>
      ) : null}

      <div className="memory-flash" aria-hidden="true" key={`flash-${index}`} />
      <div className="cinema-grain" />
      <div className="cinema-bars" aria-hidden="true" />
      <div className="memory-vignette" />

      <header className="cinema-header">
        <a className="cinema-brand" href="#top" aria-label="Rolig home">
          <Image src="/rolig-logo.png" alt="" width={36} height={36} priority />
          <span>ROLIG MEMORY ARCHIVE</span>
        </a>
        <div className="archive-status">
          <span className="live-dot" />
          {items.length || 30} APPROVED MEMES
        </div>
        <button
          className="motion-control"
          type="button"
          onClick={() => setPaused((value) => !value)}
          aria-pressed={paused}
        >
          {paused ? "Play film" : "Pause film"}
        </button>
      </header>

      <div className="memory-title-lockup">
        <p>From the internet we remember</p>
        <h1 id="cinematic-title">
          MEMORIES<br />
          <span>IN MOTION.</span>
        </h1>
      </div>

      {current ? (
        <div className="memory-caption" key={`caption-${current.id}`}>
          <span>{era}</span>
          <p>{current.summary}</p>
          <small>{current.tags.slice(0, 3).map((tag) => `#${tag}`).join(" ")}</small>
        </div>
      ) : null}

      <div className="memory-counter" aria-label={`Meme ${index + 1} of ${items.length || 30}`}>
        <strong>{String(index + 1).padStart(2, "0")}</strong>
        <span>/</span>
        <small>{String(items.length || 30).padStart(2, "0")}</small>
      </div>

      <div className="memory-progress" aria-hidden="true">
        <i style={{ width: `${progress}%` }} />
      </div>

      <a className="enter-feed" href="#try">
        <span>Scroll to enter your feed</span>
        <i aria-hidden="true">↓</i>
      </a>
    </section>
  );
}

function PhoneFeed() {
  const [phoneItems, setPhoneItems] = useState<ApprovedMeme[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError(false);

    void fetch(approvedFeedUrl, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Feed request failed: ${response.status}`);
        return response.json() as Promise<{ items: ApprovedMeme[] }>;
      })
      .then((feed) => {
        const shuffled = [...feed.items];
        for (let index = shuffled.length - 1; index > 0; index -= 1) {
          const swapIndex = Math.floor(Math.random() * (index + 1));
          [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
        }
        setPhoneItems(shuffled.slice(0, 10));
        setActiveIndex(0);
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadError(true);
        setLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey]);

  const handleScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const viewport = event.currentTarget.clientHeight;
    if (viewport === 0) return;
    const scroller = event.currentTarget;
    const rawIndex = Math.round(scroller.scrollTop / viewport);
    setActiveIndex(rawIndex);

    if (phoneItems.length > 0 && rawIndex >= phoneItems.length) {
      window.requestAnimationFrame(() => {
        scroller.scrollTop = 0;
        setActiveIndex(0);
      });
    }
  };

  const loopedPhoneItems =
    phoneItems.length > 0 ? [...phoneItems, phoneItems[0]] : [];

  return (
    <div className="phone-shell" id="try">
      <div className="phone-speaker" />
      <div
        className="phone-screen"
        aria-label="Scrollable preview of the Rolig meme feed"
        onScroll={handleScroll}
      >
        <div className="phone-topbar">
          <span>Rolig</span>
          <span className="spark">✦ For you</span>
        </div>

        {loading ? (
          <div className="phone-feed-state">
            <Image src="/rolig-logo.png" alt="" width={62} height={62} />
            <strong>Finding your vibe…</strong>
            <span>Loading approved Rolig memes</span>
          </div>
        ) : null}

        {loadError ? (
          <div className="phone-feed-state">
            <strong>The feed is waking up.</strong>
            <span>Render sometimes needs a moment.</span>
            <button type="button" onClick={() => setReloadKey((value) => value + 1)}>
              Try again
            </button>
          </div>
        ) : null}

        {loopedPhoneItems.map((item, itemIndex) => (
          <PhoneMemeSlide
            active={itemIndex === activeIndex}
            item={item}
            key={`${item.id}-${itemIndex}`}
          />
        ))}
      </div>
      <div className="scroll-hint"><span /> Scroll the feed</div>
    </div>
  );
}

function PhoneMemeSlide({
  active,
  item,
}: {
  active: boolean;
  item: ApprovedMeme;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!videoRef.current) return;
    if (active) {
      void videoRef.current.play().catch(() => undefined);
    } else {
      videoRef.current.pause();
    }
  }, [active]);

  const likes = item.likeCount && item.likeCount > 0 ? item.likeCount : "Rolig";
  const views = item.viewCount && item.viewCount > 0 ? item.viewCount : "AI";

  return (
    <article className="meme-slide phone-api-slide">
      {item.type === "video" ? (
        <video
          ref={videoRef}
          className="phone-api-media"
          src={item.url}
          autoPlay={active}
          loop
          muted
          playsInline
          preload={active ? "auto" : "metadata"}
        />
      ) : (
        // The API returns complete public Cloudflare R2 URLs.
        // eslint-disable-next-line @next/next/no-img-element
        <img className="phone-api-media" src={item.url} alt={item.summary} />
      )}

      <div className="phone-api-sheen" />
      <div className="meme-gradient" />
      <div className="meme-meta">
        <strong>@rolig_official</strong>
        <p>{item.summary}</p>
        <span>{item.tags.slice(0, 3).map((tag) => `#${tag}`).join(" ")}</span>
      </div>
      <div className="meme-actions" aria-hidden="true">
        <span>♥<small>{likes}</small></span>
        <span>↗<small>Share</small></span>
        <span>◎<small>{views}</small></span>
      </div>
    </article>
  );
}

export default function Home() {
  const [playing, setPlaying] = useState(false);

  return (
    <main>
      <nav className="nav">
        <a className="brand" href="#top" aria-label="Rolig home">
          <Image src="/rolig-logo.png" alt="" width={44} height={44} priority />
          <span>rolig</span>
        </a>
        <div className="nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#experience">Experience</a>
          <a href="#open-source">Open source</a>
        </div>
        <a className="button button-small" href="#try">
          Try Rolig <ArrowIcon />
        </a>
      </nav>

      <section className="hero" id="top">
        <div className="hero-noise" />
        <div className="hero-copy">
          <div className="eyebrow"><span>✦</span> AI-powered serotonin</div>
          <h1>Your mood.<br /><em>Your memes.</em><br />Right on time.</h1>
          <p>
            Rolig learns what makes you laugh and serves an endless feed that
            feels uncannily, delightfully yours.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="#try">
              Start scrolling <span aria-hidden="true">↓</span>
            </a>
            <a className="text-link" href={githubUrl} target="_blank" rel="noreferrer">
              View on GitHub <ArrowIcon />
            </a>
          </div>
          <div className="hero-proof">
            <div className="avatar-stack" aria-hidden="true">
              <span>😎</span><span>🤠</span><span>🥳</span>
            </div>
            <p><strong>Built in Sweden + USA + Taiwan</strong><br />For every kind of internet person</p>
          </div>
        </div>
        <div className="hero-phone">
          <div className="orbit orbit-yellow">joy</div>
          <div className="orbit orbit-coral">chaos</div>
          <PhoneFeed />
        </div>
        <div className="hero-sticker">100%<br /><strong>your vibe</strong></div>
      </section>

      <section className="marquee" aria-label="Rolig qualities">
        <div>
          <span>MEMES THAT GET YOU</span><b>✦</b>
          <span>LESS SEARCHING, MORE LAUGHING</span><b>✦</b>
          <span>POWERED BY AI, NOT ADS</span><b>✦</b>
          <span>MEMES THAT GET YOU</span><b>✦</b>
        </div>
      </section>

      <section className="mood-section section-pad">
        <div className="section-label">01 / MADE FOR YOUR BRAIN</div>
        <div className="mood-heading">
          <h2>Memes matched<br />to <span>your mood.</span></h2>
          <p>
            Not another generic feed. Rolig understands context, humor, and the
            weird little details that make a meme land exactly when you need it.
          </p>
        </div>
        <div className="mood-cards">
          <article className="mood-card card-blue">
            <span className="card-number">01</span>
            <div className="face face-laugh">XD</div>
            <h3>Tell us the vibe</h3>
            <p>Cozy? Chaotic? Deeply avoiding your inbox? We speak fluent mood.</p>
          </article>
          <article className="mood-card card-yellow">
            <span className="card-number">02</span>
            <div className="face face-think">•_•</div>
            <h3>Rolig reads the room</h3>
            <p>Every scroll, pause, and like sharpens your personal humor map.</p>
          </article>
          <article className="mood-card card-coral">
            <span className="card-number">03</span>
            <div className="face face-happy">^‿^</div>
            <h3>Instant mood lift</h3>
            <p>Get the meme you didn’t know you needed—right when it hits hardest.</p>
          </article>
        </div>
      </section>

      <section className="ai-section section-pad" id="how-it-works">
        <div className="ai-copy">
          <div className="section-label light">02 / THE SMART PART</div>
          <h2>Good taste,<br /><span>engineered.</span></h2>
          <p>
            Rolig doesn’t just count clicks. It understands the joke, the
            feeling, and why a meme works—then connects it to you.
          </p>
          <a className="button button-light" href={githubUrl} target="_blank" rel="noreferrer">
            Explore the code <ArrowIcon />
          </a>
        </div>
        <div className="ai-flow">
          <article className="ai-step">
            <div className="ai-icon">Aa</div>
            <div><span>STEP 01</span><h3>GPT analysis</h3><p>Understands visual humor, text, tone, and context—not just keywords.</p></div>
          </article>
          <div className="connector"><span>↓</span></div>
          <article className="ai-step">
            <div className="tag-cloud" aria-label="Example semantic tags">
              <span>absurdist</span><span>work life</span><span>wholesome</span>
            </div>
            <div><span>STEP 02</span><h3>Semantic tags</h3><p>Turns every meme into a rich, searchable map of meaning and mood.</p></div>
          </article>
          <div className="connector"><span>↓</span></div>
          <article className="ai-step">
            <div className="ai-icon target">◎</div>
            <div><span>STEP 03</span><h3>Your perfect match</h3><p>Recommendations adapt in real time as your vibe changes.</p></div>
          </article>
        </div>
      </section>

      <section className="experience-section section-pad" id="experience">
        <div className="experience-head">
          <div>
            <div className="section-label">03 / FEELS FAMILIAR</div>
            <h2>Zero learning curve.<br /><span>Maximum scroll.</span></h2>
          </div>
          <p>
            Built for the way you already browse: fast, fluid, full-screen, and
            ready wherever you are.
          </p>
        </div>
        <div className="feature-grid">
          <article className="feature-large">
            <div className="mini-feed" aria-hidden="true">
              <div className="mini-card mc-one">MONDAY<br />AGAIN?</div>
              <div className="mini-card mc-two">WEEKEND<br />LOADING</div>
              <div className="swipe-line">↑ SWIPE</div>
            </div>
            <div>
              <span className="feature-icon">↕</span>
              <h3>TikTok-style scrolling</h3>
              <p>One thumb. Infinite memes. Smooth vertical swiping that stays out of the way.</p>
            </div>
          </article>
          <article className="feature-small platform-card">
            <div className="device-icons" aria-hidden="true"><span>▯</span><span>▭</span><span>□</span></div>
            <div><h3>Every screen, same vibe</h3><p>Native on iOS and Android, plus a seamless web experience.</p></div>
          </article>
          <article className="feature-small fast-card">
            <div className="speedometer" aria-hidden="true"><i /></div>
            <div><h3>Fast by default</h3><p>Smart prefetching keeps the next laugh loaded before you arrive.</p></div>
          </article>
        </div>
      </section>

      <section className={`demo-section ${playing ? "is-playing" : ""}`} id="demo">
        <div className="demo-bg">
          <div className="demo-phone" aria-hidden="true">
            <Image src="/rolig-logo.png" alt="" width={160} height={160} />
          </div>
          <div className="demo-word demo-word-one">LOL</div>
          <div className="demo-word demo-word-two">MOOD</div>
          <div className="demo-word demo-word-three">SAME</div>
        </div>
        <button className="play-button" onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause demo" : "Play demo"}>
          <span>{playing ? "Ⅱ" : "▶"}</span>
        </button>
        <div className="demo-caption">
          <span>00:32</span>
          <h2>{playing ? "Okay, you get the vibe." : "See Rolig in action"}</h2>
          <p>{playing ? "The best demo is the feed above. Give it a scroll." : "A tiny tour of your new favorite scroll."}</p>
        </div>
      </section>

      <section className="opensource-section section-pad" id="open-source">
        <div className="opensource-mark">
          <Image src="/rolig-logo.png" alt="Rolig mascot" width={260} height={260} />
          <span className="taiwan-flower">✿</span>
        </div>
        <div className="opensource-copy">
          <div className="section-label">04 / OPEN BY DESIGN</div>
          <h2>Built in the open.<br /><span>Better together.</span></h2>
          <p>
            Rolig is an open-source collaboration from Taoyuan AI Lab. Read the
            code, remix the feed, report an issue, or help us make the internet
            a little funnier.
          </p>
          <div className="team-row">
            <div><strong>Taoyuan AI Lab</strong><span>Engineering · Taiwan</span></div>
            <div><strong>Community-built</strong><span>Ideas · Everywhere</span></div>
          </div>
          <a className="button button-dark" href={githubUrl} target="_blank" rel="noreferrer">
            Star us on GitHub <span aria-hidden="true">★</span>
          </a>
        </div>
      </section>

      <section className="final-cta">
        <div className="cta-scribble">↝</div>
        <div className="eyebrow"><span>✦</span> Your feed is waiting</div>
        <h2>Ready for memes<br />that actually <em>get you?</em></h2>
        <p>Come for the laughs. Stay because the algorithm has suspiciously good taste.</p>
        <div className="final-actions">
          <a className="button button-yellow" href="#try">Try the feed <span>↓</span></a>
          <a className="button button-outline" href={githubUrl} target="_blank" rel="noreferrer">GitHub <ArrowIcon /></a>
        </div>
      </section>

      <footer>
        <a className="brand footer-brand" href="#top">
          <Image src="/rolig-logo.png" alt="" width={52} height={52} />
          <span>rolig</span>
        </a>
        <p>Memes matched to your mood.</p>
        <div>
          <a href={githubUrl} target="_blank" rel="noreferrer">GitHub</a>
          <a href="#how-it-works">How it works</a>
          <a href="#top">Back to top ↑</a>
        </div>
        <small>© 2026 Rolig · Open source with good vibes.</small>
      </footer>
    </main>
  );
}
