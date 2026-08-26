# Agent Crossing portrait prompt

Use the existing portraits only for style continuity. Character identity comes
from the target persona JSON.

## Character brief

Fill these fields before generating:

- `agent_id`, Korean display name, explicit age and gender
- three visually meaningful traits
- one hobby or occupation detail that can appear in clothing or a small accessory
- distinct expression, hairstyle, clothing silhouette, and accent color
- details that must not be copied from the selected style references

Prefer ordinary adult facial diversity over beauty-standard convergence. A hobby
may inform a hat, apron, hair clip, fabric detail, or expression, but alcohol,
romance, temperament, and MBTI should not become caricatures.

## Base prompt

```text
Use case: stylized-concept
Asset type: production game UI resident portrait for Agent Crossing, an original cozy Korean village life-simulation game
Input images: Image 1..N are STYLE REFERENCES ONLY for pixel density, crop, restrained palette, warm lighting, transparent silhouette, and overall game-art finish. Do not copy their identity, face, hairstyle, clothing, pose, or accessories.
Primary request: Create one original pixel-art bust portrait of <NAME>, a Korean <GENDER> age <AGE>, characterized by <TRAITS>.
Subject: <NAME> only; <EXPRESSION>; <HAIR>; <CLOTHING>; <PERSONA-SPECIFIC VISUAL DETAIL>.
Style/medium: handcrafted 16-bit-inspired pixel art, crisp hard-edged pixel clusters, expressive original face, charming life-sim character design, moderately detailed but readable at 48px.
Composition/framing: centered square head-and-shoulders bust, front-facing with a very slight three-quarter turn, consistent generous padding, full head visible.
Lighting/mood: soft warm daylight; <CHARACTER MOOD>.
Color palette: warm cream, forest green, muted coral, earthy browns, plus <ACCENT>; restrained palette matching the parchment-and-green UI.
Scene/backdrop: genuinely transparent background around the character silhouette.
Constraints: exactly one adult human character; transparent background; no frame; no border; no text; no letters; no logo; no watermark; no prop covering the face; clean silhouette; nearest-neighbor-friendly hard pixel edges; visually distinct from every reference resident.
Avoid: copying a reference character; photorealism; direct imitation of an existing game or artist; anime rendering; 3D; smooth vector gradients; excessive dithering; blurry antialiasing; chibi child proportions; copyrighted character resemblance.
```

If the output contains a baked checkerboard, do not ask the generator to redraw
the resident. Preserve the accepted portrait and run the provided deterministic
checkerboard cleanup instead.
