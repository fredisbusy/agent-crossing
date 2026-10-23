"""말투별 대사 템플릿 (SPEC §12). 자주 나오는 화행만 말투마다 따로 둔다.

없는 (화행, 말투) 조합은 `lines.py`의 존댓말·반말 템플릿을 쓴다.
메타 단어(마음 종류를 암시하는 말)는 쓰지 않는다.
채움 필드: {event} {day} {time} {place} {item}
"""

from minds.social import Voice

VOICE_TEMPLATES: dict[tuple[str, Voice], tuple[str, ...]] = {
    # 다정한 존댓말
    ("greet", "warm"): (
        "어머, 어서 와요! 반가워요.",
        "안녕하세요! 오늘도 얼굴 보니 좋네요.",
    ),
    ("greet_again", "warm"): ("어머, 정말 오랜만이에요! 보고 싶었어요.",),
    ("smalltalk", "warm"): (
        "요즘 잘 챙겨 드시고 다니세요?",
        "오늘은 햇살이 참 포근하네요.",
        "따뜻한 차라도 한잔하고 가요.",
        "새로 들여온 원두가 향이 참 좋아요.",
        "얼굴이 좀 피곤해 보여요. 무리하지 말아요.",
        "오늘도 와 줘서 고마워요.",
    ),
    ("accept", "warm"): (
        "좋아요, {day} {time}에 {place}에서 꼭 봬요!",
        "초대해 줘서 고마워요. {event} 꼭 갈게요.",
    ),
    ("decline", "warm"): ("아쉬워라, 그 시간엔 어렵겠어요. 다음엔 꼭 같이해요.",),
    ("farewell", "warm"): (
        "살펴 가요! 또 놀러 와요.",
        "오늘 이야기 즐거웠어요. 조심히 가요.",
    ),
    ("thanks", "warm"): ("어머, 이걸 저한테요? 정말 고마워요!",),
    # 지적인 존댓말
    ("greet", "bookish"): (
        "안녕하세요. 마침 잘 오셨어요.",
        "아, 안녕하세요. 생각할 거리가 많은 하루네요.",
    ),
    ("greet_again", "bookish"): ("오랜만이네요. 그동안 어떻게 지내셨는지 궁금했어요.",),
    ("smalltalk", "bookish"): (
        "요즘 읽은 책 중에 흥미로운 대목이 있었어요.",
        "마을이 조금씩 변하는 게 눈에 보이네요.",
        "이런 날은 산책하며 생각을 정리하기 좋죠.",
        "오늘 강의 준비하다가 재미있는 자료를 찾았어요.",
        "질문을 잘 고르면 답은 절반쯤 나와 있죠.",
        "마을 사람들 이야기를 듣는 것도 공부가 돼요.",
    ),
    ("accept", "bookish"): (
        "좋습니다. {day} {time}, {place}로 가지요.",
        "흥미롭네요. {event}에 참석할게요.",
    ),
    ("decline", "bookish"): ("그 시간엔 선약이 있어서요. 아쉽네요.",),
    ("farewell", "bookish"): (
        "그럼 다음에 또 이야기 나눠요.",
        "덕분에 생각할 거리가 생겼네요. 들어가세요.",
    ),
    ("thanks", "bookish"): ("이런 걸 챙겨 주시다니, 감사합니다.",),
    # 점잖은 존댓말
    ("greet", "calm"): ("허허, 안녕하세요.", "좋은 하루입니다."),
    ("greet_again", "calm"): ("이게 얼마 만입니까. 반갑습니다.",),
    ("smalltalk", "calm"): (
        "천천히 가도 하루는 다 갑니다.",
        "오늘 같은 날씨면 마음이 놓이지요.",
        "가게 일은 늘 비슷합니다만, 그게 좋습니다.",
        "약은 제때 챙겨 드시고 계시지요?",
        "바쁠수록 쉬어 가야 합니다.",
        "저녁 공기가 선선해졌네요.",
    ),
    ("accept", "calm"): ("그러지요. {day} {time}에 {place}에서 뵙겠습니다.",),
    ("decline", "calm"): ("마음은 고맙지만 그때는 어렵겠습니다.",),
    ("farewell", "calm"): ("살펴 가십시오.", "그럼 또 뵙지요."),
    ("thanks", "calm"): ("허허, 고맙습니다. 잘 받겠습니다.",),
    # 무뚝뚝한 반말
    ("greet", "gruff"): ("왔냐.", "음, 너구나."),
    ("greet_again", "gruff"): ("얼굴 보기 힘드네, 요새.",),
    ("smalltalk", "gruff"): (
        "요즘 젊은 것들은 너무 바빠.",
        "날씨가 좋으니 무릎이 덜 쑤시는군.",
        "공원 벤치가 그나마 제일 낫지.",
        "옛날엔 이 길이 다 흙길이었어.",
        "커피는 쓴 게 제맛이지.",
        "뭐, 그럭저럭 지낸다.",
    ),
    ("accept", "gruff"): (
        "뭐, 가 주지. {day} {time}에 {place}.",
        "알았다, {event} 간다고.",
    ),
    ("decline", "gruff"): ("그땐 안 돼. 됐어.",),
    ("farewell", "gruff"): ("그럼 간다.", "들어가라."),
    ("thanks", "gruff"): ("...뭘 이런 걸 다. 고맙다.",),
    # 밝은 반말
    ("greet", "bright"): ("안녕! 마침 보고 싶었어!", "와, 여기서 만나네!"),
    ("greet_again", "bright"): ("헉, 진짜 오랜만이다! 잘 지냈어?",),
    ("smalltalk", "bright"): (
        "오늘 하늘 봤어? 완전 예쁘더라!",
        "나 요즘 새로 빠진 게임이 있어!",
        "있잖아, 오늘 기분 엄청 좋아!",
        "방금 길에서 고양이 봤어! 완전 귀여워!",
        "이따 카페 갈 건데 같이 갈래?",
        "요즘 물리 과제가 은근 재밌어!",
    ),
    ("accept", "bright"): (
        "완전 좋아! {day} {time}에 {place}에서 보자!",
        "{event}? 당연히 가지!",
    ),
    ("decline", "bright"): ("으앙, 그땐 못 가... 다음엔 꼭!",),
    ("farewell", "bright"): ("나 먼저 갈게, 또 봐!", "오늘 재밌었어! 안녕!"),
    ("thanks", "bright"): ("헉, 나 주는 거야? 대박, 고마워!",),
    # 무심한 반말
    ("greet", "cool"): ("어, 안녕.", "왔어?"),
    ("greet_again", "cool"): ("오랜만이네.",),
    ("smalltalk", "cool"): (
        "과제가 안 끝나.",
        "요즘 좀 바빠.",
        "커피나 한 잔 더 마셔야겠다.",
        "도서관 자리 맡아야 하는데.",
        "뭐, 나쁘지 않네.",
        "논문 마감이 코앞이야.",
    ),
    ("accept", "cool"): ("그래, {day} {time}. {place}.", "갈게, {event}."),
    ("decline", "cool"): ("그땐 안 돼.",),
    ("farewell", "cool"): ("간다.", "그럼 이만."),
    ("thanks", "cool"): ("...고마워.",),
    # 힘찬 반말
    ("greet", "sporty"): ("오, 안녕! 오늘도 힘내자!", "하이! 컨디션 어때?"),
    ("greet_again", "sporty"): ("오랜만! 그동안 잘 지냈지?",),
    ("smalltalk", "sporty"): (
        "아침에 공원 한 바퀴 뛰고 왔어!",
        "몸 좀 움직이면 기분이 확 달라져.",
        "요즘 연습할 곡이 산더미야. 그래도 할 만해!",
        "오늘 날씨면 야외 연주도 딱이야!",
        "스트레칭은 하고 다녀?",
        "에너지 넘치는 하루 보내자!",
    ),
    ("accept", "sporty"): (
        "좋아, {day} {time}에 {place}! 늦지 않게 갈게!",
        "{event}? 간다, 무조건!",
    ),
    ("decline", "sporty"): ("아, 그땐 연습이 있어. 미안!",),
    ("farewell", "sporty"): ("그럼 난 달려간다! 또 봐!", "파이팅! 다음에 봐!"),
    ("thanks", "sporty"): ("오, 고마워! 힘이 난다!",),
    # 몽글한 반말
    ("greet", "dreamy"): (
        "아, 안녕... 오늘 빛이 참 좋다.",
        "음, 안녕. 여기 바람 좋지?",
    ),
    ("greet_again", "dreamy"): ("오랜만이야... 꿈에서 본 것 같기도 하고.",),
    ("smalltalk", "dreamy"): (
        "저기 구름, 꼭 고래 같지 않아?",
        "오늘 색이 참 부드러워.",
        "그리고 싶은 풍경이 자꾸 생겨.",
        "물에 비친 나무가 예뻐서 한참 봤어.",
        "오늘은 노을이 무슨 색일까.",
        "작업실 창가에 햇빛이 들어.",
    ),
    ("accept", "dreamy"): (
        "좋아... {day} {time}에 {place}에서 만나.",
        "{event}, 재밌겠다. 갈게.",
    ),
    ("decline", "dreamy"): ("그땐 그림을 그려야 할 것 같아. 미안해.",),
    ("farewell", "dreamy"): ("그럼 또 봐... 좋은 하루.", "나 이제 가 볼게."),
    ("thanks", "dreamy"): ("와... 고마워. 오래 간직할게.",),
    # 초대·행사 소문·선물
    ("invite", "warm"): (
        "{day} {time}에 {place}에서 {event} 열어요. 와 주면 정말 기쁠 거예요!",
    ),
    ("share_event", "warm"): (
        "혹시 들었어요? {day} {time}에 {place}에서 {event} 한대요. 같이 가요!",
    ),
    ("gift", "warm"): ("{item} 준비했어요. 늘 고마워서요.",),
    ("invite", "bookish"): (
        "{day} {time}, {place}에서 {event} 자리가 있습니다. 함께하시겠어요?",
    ),
    ("share_event", "bookish"): (
        "알고 계세요? {day} {time}에 {place}에서 {event} 자리가 있답니다.",
    ),
    ("gift", "bookish"): (
        "작지만 {item} 준비했어요. 오늘 같은 날엔 이런 게 의미가 있죠.",
    ),
    ("invite", "calm"): (
        "{day} {time}에 {place}에서 {event} 한답니다. 시간 되시면 오시지요.",
    ),
    ("share_event", "calm"): ("{day} {time}에 {place}에서 {event} 한다고 들었습니다.",),
    ("gift", "calm"): ("허허, 별건 아니지만 {item} 받으시지요.",),
    ("invite", "gruff"): ("{day} {time}, {place}. {event}. 올 거면 와.",),
    ("share_event", "gruff"): (
        "{place}에서 {day} {time}에 {event} 한다더라. 난 뭐, 관심 없지만.",
    ),
    ("gift", "gruff"): ("자, {item}. 남아서 주는 거다.",),
    ("invite", "bright"): ("{day} {time}에 {place}에서 {event} 한대! 같이 가자, 응?",),
    ("share_event", "bright"): ("대박 소식! {day} {time}에 {place}에서 {event} 한대!",),
    ("gift", "bright"): ("짜잔! {item} 선물! 너 주려고 골랐어!",),
    ("invite", "cool"): ("{day} {time}, {place}에서 {event}. 같이 갈래?",),
    ("share_event", "cool"): ("{day} {time}에 {place}에서 {event} 한대. 참고해.",),
    ("gift", "cool"): ("이거. {item}. 그냥 받아.",),
    ("invite", "sporty"): (
        "{day} {time}에 {place}에서 {event}! 같이 가서 신나게 놀자!",
    ),
    ("share_event", "sporty"): ("소식 하나! {day} {time}에 {place}에서 {event} 한대!",),
    ("gift", "sporty"): ("{item} 받아! 기운 내라고!",),
    ("invite", "dreamy"): ("{day} {time}에 {place}에서 {event} 있대... 같이 가 볼래?",),
    ("share_event", "dreamy"): (
        "바람결에 들었는데... {day} {time}에 {place}에서 {event} 한대.",
    ),
    ("gift", "dreamy"): ("이거... {item}. 너랑 어울릴 것 같아서.",),
}
