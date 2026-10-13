# T10-C1.2-R1：116 条历史风险只读审计

执行日期：2026-10-13（Asia/Shanghai）。116 条是上一轮 production_impact.json 的 **Signal ID 集合**，逐 ID 集合一致，不是 116 条已确认错误。正式库 URI mode=ro + PRAGMA query_only，ORM autoflush=False，未修改历史状态。

|分类|数量|
|---|---:|
|CONFIRMED_ERROR|2|
|CONFIRMED_SAFE|0|
|REQUIRES_HUMAN_REVIEW|0|
|INSUFFICIENT_EVIDENCE|114|

|严重度|数量|
|---|---:|
|P0|0|
|P1|6|
|P2|110|
|UNKNOWN|0|

2 条 CONFIRMED_ERROR 仅确认已存引用偏移不等于已存正文切片，并非确认采购语义错误；其缺失历史快照仍不能恢复原事件真值。这两条已在既有隔离范围内，不是新发现未隔离 P0。其余 114 条证据不足：其中大量旧 Signal 没有正式 SignalEvidence；不能以新规则或 SUPERSEDED 状态宣布其原语义安全。CONFIRMED_SAFE / REQUIRES_HUMAN_REVIEW 为 0，是按证据条件所得，不是强制均分。所有记录仍需要真实审核，没有模型签字。

P1 为 6 条历史 APPROVED Signal，关联 3 个 Opportunity；当前三者均 INVALID_EVIDENCE，企业 validation_ready/contact_ready 均 false。华南理工历史机会仍保存 APPROVED / CONTACTED，这是历史状态，不证明当前允许触达；既有 Interaction 仅只读保护，本轮新增 0。P2 为 110 条已 SUPERSEDED、无关联当前机会的历史低风险记录；低风险仅针对当前行动影响，不等于确认原信号正确。

当前 Actionability：{'INVALID_EVIDENCE': 12, 'NOT_ACTIONABLE': 99, 'UNKNOWN': 2, 'WATCH': 3}。已证实影响当前可行动机会的 P0=0；不能由此宣布历史风险清零。汉邦激光仍按原 6/9/16/4 隔离门禁禁止验证与联系。

完整机器材料：[risk_audit.json](D:/myAI/bizpulse/docs/reports/t10_c1_2_r1/risk_audit.json)。包含真实 ID、旧规则/payload、重算诊断、记录版本/正文哈希/快照存在性、准确引用/偏移、历史审核日志、痛点与候选关联、下游机会及其他信号、当前行动及就绪状态。保留的 history_stored_text 只复制正式库已存正文，不替代缺失历史 HTML。

|Signal ID|SourceRecord|旧类型/状态|分类 / 严重度|Evidence IDs|Opportunity IDs|Actionability|验证/联系|
|---|---|---|---|---|---|---|---|
|sig_68b991dd24d3469a9289a88a|rec_1d19516678e64748a9094e7a|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|INVALID_EVIDENCE|False/False|
|sig_70fd0fa9fbdf44dfb1241740|rec_1d19516678e64748a9094e7a|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|INVALID_EVIDENCE|False/False|
|sig_3574b77ca46a43cc922f69d0|rec_1d19516678e64748a9094e7a|PROCUREMENT/APPROVED|INSUFFICIENT_EVIDENCE/P1|sev_3414e62bb5b446a5a0ff5780|opp_4638d8172f5d4c6cb626a0a3|INVALID_EVIDENCE|False/False|
|sig_0230f2f4df6e4c3e982fb7cc|rec_1d19516678e64748a9094e7a|TENDER/APPROVED|CONFIRMED_ERROR/P1|sev_bbcb2ed3f1df49afbbbdfd95|opp_4638d8172f5d4c6cb626a0a3|INVALID_EVIDENCE|False/False|
|sig_9d4c412c88cf4287a0f78753|rec_ded5daf70ede4a81940b73b7|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|INVALID_EVIDENCE|False/False|
|sig_f6408351055744a082275361|rec_ded5daf70ede4a81940b73b7|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|INVALID_EVIDENCE|False/False|
|sig_191612e28e364952887f4ac2|rec_ded5daf70ede4a81940b73b7|PROCUREMENT/APPROVED|INSUFFICIENT_EVIDENCE/P1|sev_70a4d3cf3b5d492491368b6f|opp_3c5d39b31bf2457092dc7745|INVALID_EVIDENCE|False/False|
|sig_6294bfb3ef9049258b00bbbb|rec_ded5daf70ede4a81940b73b7|TENDER/APPROVED|INSUFFICIENT_EVIDENCE/P1|sev_1c5b3b39498445b2b2fb8a91|opp_3c5d39b31bf2457092dc7745|INVALID_EVIDENCE|False/False|
|sig_ac469ca2fdc74f01bcb5c6ed|rec_23cfcd8847014b0cafc27bc9|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|INVALID_EVIDENCE|False/False|
|sig_f06750dfc52941dc861bacf3|rec_23cfcd8847014b0cafc27bc9|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|INVALID_EVIDENCE|False/False|
|sig_d7897094861049b69a5ceb11|rec_23cfcd8847014b0cafc27bc9|PROCUREMENT/APPROVED|INSUFFICIENT_EVIDENCE/P1|sev_17e992c86cb140b599327d09|opp_735c89c4222a466bbf1e1596|INVALID_EVIDENCE|False/False|
|sig_efa34800e1ff42829b9c0ba6|rec_23cfcd8847014b0cafc27bc9|TENDER/APPROVED|CONFIRMED_ERROR/P1|sev_69c5cec6f1374fa19eb17473|opp_735c89c4222a466bbf1e1596|INVALID_EVIDENCE|False/False|
|sig_1add130be91c4e2494954349|rec_5a1b7f02b7554ba3870c52bb|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_873b67c3fc6b4cc3842b3722|rec_5a1b7f02b7554ba3870c52bb|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_afea8d4b5d034ce89a6cf48d|rec_c87bbd78b02148a4b3eaf274|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_1cb32ec0c51249708555eca4|rec_c87bbd78b02148a4b3eaf274|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_52d726219ca742d9a1af02f4|rec_4c451dc769074734b76d93ef|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a37942a3ff254c3b993962bb|rec_4c451dc769074734b76d93ef|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_0a7098a1744241e5926a9d09|rec_683aa61b1c8c46e58b40c3f8|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_2def0ac195b145ba9ce1f181|rec_683aa61b1c8c46e58b40c3f8|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_377ee44c8e4b4521bcd99100|rec_692ba4500004471995c8c78c|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_faf3ff6915744a9f8878ef78|rec_692ba4500004471995c8c78c|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d21f0fe0a9844520a5baea8e|rec_1fd9903532b44cb180ecc045|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_db119c1d0ffa4a1dbb30aa90|rec_1fd9903532b44cb180ecc045|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_9eaa942c0ef04b2082e59ebf|rec_36241c668151483281cc8c18|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_6886322c002e4c048b1f8657|rec_36241c668151483281cc8c18|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_091ec68dd5044e8c875bfcf5|rec_766f6263a94c47398b612e3c|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_fc7eab8c2f0649a7860d7430|rec_766f6263a94c47398b612e3c|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_0a854f964c794549bbb59548|rec_6c1b48dd32fd425cadf4b9aa|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_ea6223e886c940b0a05eeebd|rec_6c1b48dd32fd425cadf4b9aa|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_024a46beb1fc414bba9ef6b5|rec_6b95d3ceccd34381acbec9f0|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_e2ae0e266ace4353923f2103|rec_6b95d3ceccd34381acbec9f0|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a558223d7ec84f738d9f3d2f|rec_d1b5ab455d9b41138fadf2cf|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_8ecc2a57e94f4171ba46cfae|rec_d1b5ab455d9b41138fadf2cf|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_82e96229880c4e77a2836ca7|rec_0dc406bcbdf544d38a087244|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a09b26f9e53f456a84f43827|rec_0dc406bcbdf544d38a087244|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d97f93916e78476ca5c4103b|rec_5629892728f5412fbd01668a|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d8f055af028e4436a89954c9|rec_5629892728f5412fbd01668a|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_24793741083f4d8aa5c262b1|rec_f6a38c878fe443c1b5db0a39|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_2e501dd0847f4b82a2e746d2|rec_f6a38c878fe443c1b5db0a39|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_5f0596751b624bbaa76d1bee|rec_15183fa352a544beb98c74ac|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_385dbf226cbb4fb884c2e6a0|rec_15183fa352a544beb98c74ac|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_92e2f943aefb408097c55acb|rec_e834408f85504262805f3d94|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_ce403dbaf5bb48888af93a7a|rec_e834408f85504262805f3d94|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_68c4b52bce6842609028861a|rec_8ddd97b176434773bd4b571c|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_97dec9862e9e4907b41c5114|rec_8ddd97b176434773bd4b571c|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_c714d98dba214b1e9621abe0|rec_f1de0857a47a49f9a2312a2d|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_b50409aa5b8c42cb9c141971|rec_f1de0857a47a49f9a2312a2d|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_5ca75df07c55402a9a3fdda3|rec_cfe30e07d0f34d948a943827|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_556de603de6e4bc2a9e00f67|rec_cfe30e07d0f34d948a943827|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_fbc91ccaa109480ab5dc0c53|rec_05f99e1b7126491e8b63b2a2|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_90d10259b2524a8b96b3ddc1|rec_05f99e1b7126491e8b63b2a2|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_67b59ab33c4f4ac3afd5746f|rec_825f7bbf4220496eabe78914|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_3923910869fb4184922d98b8|rec_825f7bbf4220496eabe78914|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_9e64fed5e81e4ea1b158102d|rec_037eb8955b9e49e3adef1fa4|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_cc2b63c5642644a398a7ea21|rec_037eb8955b9e49e3adef1fa4|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_01c4a491ecd845dd83698f75|rec_6be45448ddac416cba5a24b6|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_ba963d22d3e3428cb91db219|rec_ad7c69b637de4750b86a5a7d|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_4a0f795c609b4e6d9b26f92b|rec_b2d4e5e42354413395aafae1|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_91b58630184d4e2db35e5bb6|rec_38068ef58a6f4ea6846b719e|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_eab3f46c3bab4479b68edd03|rec_7bc02e819d924da793cf4150|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a9de0409a50e4c77b768f0f2|rec_957aecf3ed3d4784b0d1ae26|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_1afed735e2974368b96c3c11|rec_f9156a63be5f462885e5dd15|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d3fdfc93f97d4bcdb6ad93e1|rec_ef1b4b27c83e43d98d410a51|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_b507e177bd9e4538a1fd1a1f|rec_3f54ffaa604e49f99b7f3cad|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a0df9b9a67f748c58452c418|rec_5b7f8ddd0a2a40488930a52e|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_bf17c61523aa425d8b2d294d|rec_35fdbf15cd7d4b07b0f889d5|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_332cf64f91674348a9f4c5f6|rec_fd35ccf3ae2945b4bd032a5d|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_711192181e1044d681515407|rec_a95ce72b98be4491abbc460b|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_be0b6872a2a74fbdb5e6fb4b|rec_95a64006265b4d51a61a02d7|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_4e7952873e1e4650acbfb073|rec_95a64006265b4d51a61a02d7|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_5fc9d2d1f8dc43efb3c8f355|rec_4016e0374aaa4479b2cc68aa|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a2c47b707e6946d3804871e9|rec_4016e0374aaa4479b2cc68aa|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d4747327474947419287541f|rec_e7c5e656d4e24452bd719f03|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_1f2a86048ab3470e894743c7|rec_e7c5e656d4e24452bd719f03|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_043c4aecbd4441a78f1a3edb|rec_5a75eea61e0c4941a7dba8d0|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_ea1b28d6c3894c6c9f32d7aa|rec_5a75eea61e0c4941a7dba8d0|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_ab4fda9c37754eb2bbd95e35|rec_e87221f0288f440a8b8d7050|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a6293e082c81450f9245c6bb|rec_e87221f0288f440a8b8d7050|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d69b50932d2d4d3fb80d4661|rec_c11910e66c784215892db840|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_565692bffd7e4b92a4c3c18a|rec_c11910e66c784215892db840|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_685d8ba8a5c44edfafcdc333|rec_fd11057562774041856c80ff|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_95d40115d6c446809175d6b5|rec_fd11057562774041856c80ff|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_e6476cc88d32487ab6723074|rec_35f9a91c3b514289b8850ee5|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_20d6572ce687416f8f55d696|rec_35f9a91c3b514289b8850ee5|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_c8847a01bb4b4434a490e75f|rec_e99d7a25a8f340c2ab16906e|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a47e8a9f73c041bda39030cb|rec_e99d7a25a8f340c2ab16906e|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_6eea234215a7477e91440b8c|rec_186d79098c2d4ad7b29ad868|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_466b7a6d30104d6f9cdb9214|rec_186d79098c2d4ad7b29ad868|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d65b667b4e864b5c80def2d2|rec_fa2dc8a976bf4cef82efe0c4|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_87799a6d7663402e90e2b247|rec_fa2dc8a976bf4cef82efe0c4|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_b0416a99ad764464ac500529|rec_7baa3ee5fb83475ebe0084f8|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_8aec213147264ed6a6296fa6|rec_7baa3ee5fb83475ebe0084f8|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_92137dd811bd4922a58e7214|rec_2dbfca3a5ece4aa5b8cee67e|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a1dbf7542a0841cb8d5b739c|rec_2dbfca3a5ece4aa5b8cee67e|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_7b0aefbb805c4e659029be77|rec_dd218a65da6046dd9c454833|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_19c8c729faee4a45a0997ccc|rec_dd218a65da6046dd9c454833|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_65e4fabe46244b368734b171|rec_1c81e4e031a7492f95ea95aa|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_f90d8066ee6844f382b3d8f6|rec_1c81e4e031a7492f95ea95aa|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_d312390137324b798a89ab27|rec_880c4f17374b48bab8373103|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_323ecaa880da4e519b2581e9|rec_880c4f17374b48bab8373103|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_c66b7ae321a346469e305483|rec_256459702d554cc9996a5858|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_f4a9a946a2134f87b56e52c4|rec_256459702d554cc9996a5858|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_a64bb8b936a84f61b5c036a1|rec_23c269faca24411f9214528b|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_8524c4bec1bc408986ded22d|rec_23c269faca24411f9214528b|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_9399c25be4c548829ea5657a|rec_691e3d3ebc564a969764bc80|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_3aec5b2fd2644864a3b9e973|rec_691e3d3ebc564a969764bc80|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_6a8b95a1c4384c2191603313|rec_c2dacf3a7a8a42fba6fa77ac|TENDER/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_9b443798e2e14278b7457cd3|rec_c2dacf3a7a8a42fba6fa77ac|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_e9162ca75b1f4c8ca823a07f|rec_4876f7c5e87641bda77962c1|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_7e932fee108c404290302cca|rec_940a7223e13b4f47bb78d5ac|PROCUREMENT/SUPERSEDED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|NOT_ACTIONABLE|False/False|
|sig_42477d1f5a67404fbc4b6ac0|rec_903ed1b4140d45699ac04a02|PROCUREMENT/REJECTED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|UNKNOWN|False/False|
|sig_2e5fdbc554314c1b8baffb7b|rec_b141d717c13f4ca7ad49438f|CRM_DEMAND/REJECTED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|WATCH|False/False|
|sig_d49f7eeddd364962b7d684ae|rec_b141d717c13f4ca7ad49438f|ERP_DEMAND/REJECTED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|WATCH|False/False|
|sig_dbf784b1b55744a6a52d994b|rec_4b7ba7c4318b4b609639e870|PROCUREMENT/REJECTED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|UNKNOWN|False/False|
|sig_6a9d5c2429a84594990fd05b|rec_4b7ba7c4318b4b609639e870|CRM_DEMAND/REJECTED|INSUFFICIENT_EVIDENCE/P2|NONE|NONE|WATCH|False/False|

## 逐条依据与下游

### sig_68b991dd24d3469a9289a88a

- 原始来源：[中国科学院理论物理研究所高性能计算机时采购项目公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435469.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`f2c646d253333fc51ef2f7e7a50482d096098c6060e98523679ffa690c48faa6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_70fd0fa9fbdf44dfb1241740

- 原始来源：[中国科学院理论物理研究所高性能计算机时采购项目公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435469.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`f2c646d253333fc51ef2f7e7a50482d096098c6060e98523679ffa690c48faa6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_3574b77ca46a43cc922f69d0

- 原始来源：[中国科学院理论物理研究所高性能计算机时采购项目公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435469.htm)；企业：中国科学院理论物理研究所。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`f2c646d253333fc51ef2f7e7a50482d096098c6060e98523679ffa690c48faa6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：['pain_1260f2d0f2774802b6a01b96']；OpportunityCandidate：[{'id': 'ocand_471cc1407bd94254ba5e6b68', 'status': 'CONVERTED'}]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_0230f2f4df6e4c3e982fb7cc

- 原始来源：[中国科学院理论物理研究所高性能计算机时采购项目公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435469.htm)；企业：中国科学院理论物理研究所。
- 分类依据：Stored evidence slice mismatch: sev_bbcb2ed3f1df49afbbbdfd95；原版本快照：False；版本：1；正文 SHA256：`f2c646d253333fc51ef2f7e7a50482d096098c6060e98523679ffa690c48faa6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：['pain_1260f2d0f2774802b6a01b96']；OpportunityCandidate：[{'id': 'ocand_471cc1407bd94254ba5e6b68', 'status': 'CONVERTED'}]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_9d4c412c88cf4287a0f78753

- 原始来源：[清华大学低温强磁场扫描隧道显微镜公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435451.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2aeae5f6ff01bb63f96898d2b2ce604ca1e90159c00462f0fbf0359e8b06f7e6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_f6408351055744a082275361

- 原始来源：[清华大学低温强磁场扫描隧道显微镜公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435451.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2aeae5f6ff01bb63f96898d2b2ce604ca1e90159c00462f0fbf0359e8b06f7e6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_191612e28e364952887f4ac2

- 原始来源：[清华大学低温强磁场扫描隧道显微镜公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435451.htm)；企业：清华大学。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2aeae5f6ff01bb63f96898d2b2ce604ca1e90159c00462f0fbf0359e8b06f7e6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：['pain_bc207e987fd14b2786bb5ac4']；OpportunityCandidate：[{'id': 'ocand_d3abec121dc54427832c7d21', 'status': 'CONVERTED'}]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_6294bfb3ef9049258b00bbbb

- 原始来源：[清华大学低温强磁场扫描隧道显微镜公开招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435451.htm)；企业：清华大学。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2aeae5f6ff01bb63f96898d2b2ce604ca1e90159c00462f0fbf0359e8b06f7e6`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：['pain_bc207e987fd14b2786bb5ac4']；OpportunityCandidate：[{'id': 'ocand_d3abec121dc54427832c7d21', 'status': 'CONVERTED'}]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_ac469ca2fdc74f01bcb5c6ed

- 原始来源：[华南理工大学低温超高真空扫描隧道显微镜（SCUT-HW-ZB20260011号）招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435453.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`a13b3da9bc62d85e0b0aa16390f2f7aaef38d14c3c0db747f8d16ec4a18d9c6d`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_f06750dfc52941dc861bacf3

- 原始来源：[华南理工大学低温超高真空扫描隧道显微镜（SCUT-HW-ZB20260011号）招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435453.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`a13b3da9bc62d85e0b0aa16390f2f7aaef38d14c3c0db747f8d16ec4a18d9c6d`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d7897094861049b69a5ceb11

- 原始来源：[华南理工大学低温超高真空扫描隧道显微镜（SCUT-HW-ZB20260011号）招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435453.htm)；企业：华南理工大学。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`a13b3da9bc62d85e0b0aa16390f2f7aaef38d14c3c0db747f8d16ec4a18d9c6d`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：['pain_3575e65e364749eda1040834']；OpportunityCandidate：[{'id': 'ocand_29df76a8e3df4b02a5c2f2b5', 'status': 'CONVERTED'}]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_efa34800e1ff42829b9c0ba6

- 原始来源：[华南理工大学低温超高真空扫描隧道显微镜（SCUT-HW-ZB20260011号）招标公告](http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435453.htm)；企业：华南理工大学。
- 分类依据：Stored evidence slice mismatch: sev_69c5cec6f1374fa19eb17473；原版本快照：False；版本：1；正文 SHA256：`a13b3da9bc62d85e0b0aa16390f2f7aaef38d14c3c0db747f8d16ec4a18d9c6d`。
- 证据问题：['INVALID_EVIDENCE', 'INVALID_EVIDENCE_DEPENDENCY', 'MISSING_SOURCE_SNAPSHOT']；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：['pain_3575e65e364749eda1040834']；OpportunityCandidate：[{'id': 'ocand_29df76a8e3df4b02a5c2f2b5', 'status': 'CONVERTED'}]；审批日志 3 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_1add130be91c4e2494954349

- 原始来源：[清华大学67GHz矢量信号发生器中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435527.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`f83254df210d4cf4a8c4e01f00dbf9c4239099f4541d6d299f3f654252ce9ba7`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_873b67c3fc6b4cc3842b3722

- 原始来源：[清华大学67GHz矢量信号发生器中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435527.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`f83254df210d4cf4a8c4e01f00dbf9c4239099f4541d6d299f3f654252ce9ba7`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_afea8d4b5d034ce89a6cf48d

- 原始来源：[清华大学110GHz连续扫描矢量网络分析仪中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435526.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`7dd1d4969419bdae9754bb02626b0c7e0a7d8c0ab5ed8e5a875b16b70f8eb803`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_1cb32ec0c51249708555eca4

- 原始来源：[清华大学110GHz连续扫描矢量网络分析仪中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435526.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`7dd1d4969419bdae9754bb02626b0c7e0a7d8c0ab5ed8e5a875b16b70f8eb803`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_52d726219ca742d9a1af02f4

- 原始来源：[清华大学真空系统采购项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435284.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`8f8ea92708af74c3f075d4630fcc08f4c565b5ccd7113f904197c0a7622b0110`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a37942a3ff254c3b993962bb

- 原始来源：[清华大学真空系统采购项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435284.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`8f8ea92708af74c3f075d4630fcc08f4c565b5ccd7113f904197c0a7622b0110`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_0a7098a1744241e5926a9d09

- 原始来源：[四川省凉山州消防救援支队2026年度城乡独居老人免费安装联网型独立感烟火灾报警器建设项目（第三次）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435271.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`401406ebbea055add5df7eb4613a2507daf280701dc3e2228befa6c5a171c349`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_2def0ac195b145ba9ce1f181

- 原始来源：[四川省凉山州消防救援支队2026年度城乡独居老人免费安装联网型独立感烟火灾报警器建设项目（第三次）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435271.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`401406ebbea055add5df7eb4613a2507daf280701dc3e2228befa6c5a171c349`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_377ee44c8e4b4521bcd99100

- 原始来源：[清华大学1064nm激光器采购项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435266.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`b11f957620d14b79ee3597fd19625e3cc32c85a269d3bff3a18fcc58e818abe1`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_faf3ff6915744a9f8878ef78

- 原始来源：[清华大学1064nm激光器采购项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435266.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`b11f957620d14b79ee3597fd19625e3cc32c85a269d3bff3a18fcc58e818abe1`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d21f0fe0a9844520a5baea8e

- 原始来源：[钛板模具采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435192.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`5e703704a0e1849b01c865a2d3551afaefd9c376d970c58ef8bc0a45238df783`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_db119c1d0ffa4a1dbb30aa90

- 原始来源：[钛板模具采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435192.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`5e703704a0e1849b01c865a2d3551afaefd9c376d970c58ef8bc0a45238df783`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_9eaa942c0ef04b2082e59ebf

- 原始来源：[井筒流量传感器标定设备采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435185.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`bca7c7df6ae4ae868524d14e093918808075c0412300ca71cb47f8a828edb705`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_6886322c002e4c048b1f8657

- 原始来源：[井筒流量传感器标定设备采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435185.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`bca7c7df6ae4ae868524d14e093918808075c0412300ca71cb47f8a828edb705`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_091ec68dd5044e8c875bfcf5

- 原始来源：[井下光缆定位设备采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435194.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`ed36b0c59e4f41efa8653e23c6a970053272e062709d1d8d45027799698ed65b`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_fc7eab8c2f0649a7860d7430

- 原始来源：[井下光缆定位设备采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435194.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`ed36b0c59e4f41efa8653e23c6a970053272e062709d1d8d45027799698ed65b`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_0a854f964c794549bbb59548

- 原始来源：[东南大学物理学院高功率紫外超快光量子发射系统采购中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435026.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`ce16416c643c2310418772782265f0462e5b2889f57978708102d714ab39f393`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_ea6223e886c940b0a05eeebd

- 原始来源：[东南大学物理学院高功率紫外超快光量子发射系统采购中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27435026.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`ce16416c643c2310418772782265f0462e5b2889f57978708102d714ab39f393`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_024a46beb1fc414bba9ef6b5

- 原始来源：[中南大学后勤保障部饮食服务中心食用油配送服务项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434964.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`55181f2a47c8d0ded6b3adb9c93d4c927494873e382f9446096c7f335c548fb0`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_e2ae0e266ace4353923f2103

- 原始来源：[中南大学后勤保障部饮食服务中心食用油配送服务项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434964.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`55181f2a47c8d0ded6b3adb9c93d4c927494873e382f9446096c7f335c548fb0`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a558223d7ec84f738d9f3d2f

- 原始来源：[海关总署2026年-2029年制式皮鞋加工服务采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434995.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e47157d2496e491612dcc2b035e4da668bbe737276fea3127690b7ee968309a3`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_8ecc2a57e94f4171ba46cfae

- 原始来源：[海关总署2026年-2029年制式皮鞋加工服务采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434995.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e47157d2496e491612dcc2b035e4da668bbe737276fea3127690b7ee968309a3`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_82e96229880c4e77a2836ca7

- 原始来源：[智能运维系统采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434752.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2b225f43c4dcbb2be587ee6cc9cf0d311afa2853a2de8f06bbcec991dade65ca`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a09b26f9e53f456a84f43827

- 原始来源：[智能运维系统采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434752.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2b225f43c4dcbb2be587ee6cc9cf0d311afa2853a2de8f06bbcec991dade65ca`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d97f93916e78476ca5c4103b

- 原始来源：[永久园区冰箱、净水器等电器物资采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434747.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`0f122d7e6c63e583c2e8e6345f6a30d751ec82587c6b852ad9456d35d122d33e`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d8f055af028e4436a89954c9

- 原始来源：[永久园区冰箱、净水器等电器物资采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434747.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`0f122d7e6c63e583c2e8e6345f6a30d751ec82587c6b852ad9456d35d122d33e`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_24793741083f4d8aa5c262b1

- 原始来源：[海南税务2026年区块链国有土地使用权出让收入场景优化升级、金四多云运维管理平台及金税三期系统等运行维护项目(二次)结果公告（采购包1）](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434683.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e62dfa121011ecd2e0f02dc2984a741c1c45b72836b51c205c011b7b395d37f5`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_2e501dd0847f4b82a2e746d2

- 原始来源：[海南税务2026年区块链国有土地使用权出让收入场景优化升级、金四多云运维管理平台及金税三期系统等运行维护项目(二次)结果公告（采购包1）](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434683.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e62dfa121011ecd2e0f02dc2984a741c1c45b72836b51c205c011b7b395d37f5`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_5f0596751b624bbaa76d1bee

- 原始来源：[全国海关信息中心2026年非贸一体化风险智能甄别模型技术服务采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434685.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`cfb058cd34816d9c6271eee5f7c0cbe74bbd8e3c5b3f8ad165c213dcff7b9cff`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_385dbf226cbb4fb884c2e6a0

- 原始来源：[全国海关信息中心2026年非贸一体化风险智能甄别模型技术服务采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434685.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`cfb058cd34816d9c6271eee5f7c0cbe74bbd8e3c5b3f8ad165c213dcff7b9cff`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_92e2f943aefb408097c55acb

- 原始来源：[江西省机电设备招标有限公司关于南昌消防救援机动支队无人机采购项目（项目编号：JXTC2026040404）第二次招标中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434505.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`32bea085f272310b10b32b331972ff789fed802593bff19f067a6e95a09b61ce`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_ce403dbaf5bb48888af93a7a

- 原始来源：[江西省机电设备招标有限公司关于南昌消防救援机动支队无人机采购项目（项目编号：JXTC2026040404）第二次招标中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434505.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`32bea085f272310b10b32b331972ff789fed802593bff19f067a6e95a09b61ce`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_68c4b52bce6842609028861a

- 原始来源：[同济大学临港新校区公共学习中心项目全过程跟踪审计采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434503.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`024bcbacea8c92938c624087756e4f803d9872621e876f02a7dac8016885cd0f`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_97dec9862e9e4907b41c5114

- 原始来源：[同济大学临港新校区公共学习中心项目全过程跟踪审计采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434503.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`024bcbacea8c92938c624087756e4f803d9872621e876f02a7dac8016885cd0f`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_c714d98dba214b1e9621abe0

- 原始来源：[同济大学临港新校区本科生生活区一期项目全过程跟踪审计采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434513.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`22efa610910b48be7981cf508a7a4113c64116cf444c63bdb8386a79a464b87a`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_b50409aa5b8c42cb9c141971

- 原始来源：[同济大学临港新校区本科生生活区一期项目全过程跟踪审计采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434513.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`22efa610910b48be7981cf508a7a4113c64116cf444c63bdb8386a79a464b87a`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_5ca75df07c55402a9a3fdda3

- 原始来源：[轮台县消防救援大队拉依苏消防站室外跑道改造项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434416.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`647c1440207d300ad4bb962e3e56b693652b34ed4a135439c0e21c125baee603`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_556de603de6e4bc2a9e00f67

- 原始来源：[轮台县消防救援大队拉依苏消防站室外跑道改造项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434416.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`647c1440207d300ad4bb962e3e56b693652b34ed4a135439c0e21c125baee603`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_fbc91ccaa109480ab5dc0c53

- 原始来源：[国家金融监督管理总局巴音郭楞监管分局巴音郭楞金融监管分局办公楼修缮项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434397.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`6cbd222bc37e88943de5a45435c3c7e63dfec72ac044b3fa16fe1897f6d75bdd`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_90d10259b2524a8b96b3ddc1

- 原始来源：[国家金融监督管理总局巴音郭楞监管分局巴音郭楞金融监管分局办公楼修缮项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434397.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`6cbd222bc37e88943de5a45435c3c7e63dfec72ac044b3fa16fe1897f6d75bdd`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_67b59ab33c4f4ac3afd5746f

- 原始来源：[财政部发布2025年全国政府采购简要情况_中国政府采购网](http://www.ccgp.gov.cn/news/202609/t20260928_27408954.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`f862b2eb3f75ceb08d60ee011b2b8dc6caf2bffb28248ca6570145a48b1f1d32`。
- 证据问题：[]；新规则仅诊断：DEMAND_INFERRED；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_3923910869fb4184922d98b8

- 原始来源：[财政部发布2025年全国政府采购简要情况_中国政府采购网](http://www.ccgp.gov.cn/news/202609/t20260928_27408954.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`f862b2eb3f75ceb08d60ee011b2b8dc6caf2bffb28248ca6570145a48b1f1d32`。
- 证据问题：[]；新规则仅诊断：DEMAND_INFERRED；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_9e64fed5e81e4ea1b158102d

- 原始来源：[财政部 应急管理部联合印发《紧急采购管理暂行办法》_中国政府采购网](http://www.ccgp.gov.cn/news/202609/t20260911_27314679.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`9c1dc874b9a5aec44293c59aec68db56ce30edfb0dd6a0a871928f671693aac4`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_cc2b63c5642644a398a7ea21

- 原始来源：[财政部 应急管理部联合印发《紧急采购管理暂行办法》_中国政府采购网](http://www.ccgp.gov.cn/news/202609/t20260911_27314679.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`9c1dc874b9a5aec44293c59aec68db56ce30edfb0dd6a0a871928f671693aac4`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_01c4a491ecd845dd83698f75

- 原始来源：[国办发文治理中小企业回款难 政府采购不得以商业汇票等替代现金支付_中国政府采购网](http://www.ccgp.gov.cn/news/202609/t20260911_27309577.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`8eff39879c2d347c64275fb35953c0e192c24e27fe0acbc677e259128e7ba4d4`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_ba963d22d3e3428cb91db219

- 原始来源：[“开局起步‘十五五’”系列主题新闻发布会举行 财政部副部长廖岷回应政府采购热点_中国政府采购网](http://www.ccgp.gov.cn/news/202608/t20260825_27195598.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e57b8c730228122fc890eed33ea9bb1a47df4f8e1bd4ac10d5ddd2ccc9f333a8`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_4a0f795c609b4e6d9b26f92b

- 原始来源：[财政部公布2026年政府采购代理机构检查名单_中国政府采购网](http://www.ccgp.gov.cn/news/202607/t20260715_26935390.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2208454c0d357de6eeda8e83e784648f483cf376647e848e34a562825c673ae6`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_91b58630184d4e2db35e5bb6

- 原始来源：[财政部国库司与英国能源安全与净零部工业脱碳与碳排放交易司开展政府绿色采购政策交流_中国政府采购网](http://www.ccgp.gov.cn/zcdt/202510/t20251030_25601258.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`766bfa44853d223833c3b42a87554afa844f668dfb89233add3b296fb89f066b`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_eab3f46c3bab4479b68edd03

- 原始来源：[海南首例政府采购全流程AI评审落地_中国政府采购网](http://www.ccgp.gov.cn/zcdt/202609/t20260930_27433997.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`47a8acc152aac41b587b28a12b22b0bb2d8533c603541fd7c0e239e2459566ad`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a9de0409a50e4c77b768f0f2

- 原始来源：[海南首例政府采购工程“机器评审”顺利实施_中国政府采购网](http://www.ccgp.gov.cn/zcdt/202609/t20260930_27433576.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`1a1ede301e9728ed3388d4a9cf6b8af5572278fe7fef45d975d9f092e431994d`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_1afed735e2974368b96c3c11

- 原始来源：[吉林集采机构竞争改革再升级_中国政府采购网](http://www.ccgp.gov.cn/zcdt/202609/t20260922_27375527.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e638350354ed49a65dcf38dc7160fbe28dff54561f9bb6b78c6265714b29ff44`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d3fdfc93f97d4bcdb6ad93e1

- 原始来源：[内蒙古持续推进政采制度改革培训_中国政府采购网](http://www.ccgp.gov.cn/zcdt/202609/t20260922_27375526.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`56c88005320f2efcd63c6b4a7cac93a6b50d7e531bd3cb3a7045f62d81863269`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_b507e177bd9e4538a1fd1a1f

- 原始来源：[甘肃省财政厅推动政府购买服务改革走深走实_中国政府采购网](http://www.ccgp.gov.cn/gpsr/zhxx/df/202607/t20260708_26892820.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`50c5898b876d04cd218f2ddd89869358d5ff5b958d212986c9432f3a77220169`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a0df9b9a67f748c58452c418

- 原始来源：[四川省财政厅：深化政府购买服务改革 让公共服务“买得值”又“用得好”_中国政府采购网](http://www.ccgp.gov.cn/gpsr/zhxx/df/202607/t20260708_26892813.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`4f04bfd4043a19182a5324bf7a02289fa7e985d5add395ae84ad8bd6610ea703`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_bf17c61523aa425d8b2d294d

- 原始来源：[坚定改革信心 走深走实北京政府购买服务改革之路_中国政府采购网](http://www.ccgp.gov.cn/gpsr/zhxx/df/202603/t20260312_26261484.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`18a9742e35556cd1422251d0c1bcd0e58e529fad915aa1fec21ef3147d4a76a0`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_332cf64f91674348a9f4c5f6

- 原始来源：[广东将低空经济服务纳入政府购买服务范围_中国政府采购网](http://www.ccgp.gov.cn/gpsr/zhxx/df/202511/t20251114_25695352.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`696946f36157e9d268c8d6cd9df00da19ad35498dc2a97b3267054bc67d028aa`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_711192181e1044d681515407

- 原始来源：[重庆市进一步加强政府购买服务管理_中国政府采购网](http://www.ccgp.gov.cn/gpsr/zhxx/df/202510/t20251029_25593122.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`929eb59e25af7ab9e02c3c790e9e529fd5c4e6ae46c1cd9ab229b42d38b86a8e`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_be0b6872a2a74fbdb5e6fb4b

- 原始来源：[中国地质大学（北京）电感耦合等离子体质谱仪采购项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434331.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`9ee142a1d7b93eeefa0d677d152c872d172ae82ffd136c6360437a7085359591`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_4e7952873e1e4650acbfb073

- 原始来源：[中国地质大学（北京）电感耦合等离子体质谱仪采购项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434331.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`9ee142a1d7b93eeefa0d677d152c872d172ae82ffd136c6360437a7085359591`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_5fc9d2d1f8dc43efb3c8f355

- 原始来源：[国家税务总局咸阳市秦都区税务局综合业务办公用房维修项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434200.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`21495cb00b41b7b61ddfdc1d1f685d74892c6eac4e74c95bbfbef365e663b229`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a2c47b707e6946d3804871e9

- 原始来源：[国家税务总局咸阳市秦都区税务局综合业务办公用房维修项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434200.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`21495cb00b41b7b61ddfdc1d1f685d74892c6eac4e74c95bbfbef365e663b229`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d4747327474947419287541f

- 原始来源：[柯坪县消防救援大队2026年伙食采购及配送项目（二次）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434136.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`eff2db891b4db46d309d3f4d3d2a88a1f404e26b2140b4e48412a6b82e683962`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_1f2a86048ab3470e894743c7

- 原始来源：[柯坪县消防救援大队2026年伙食采购及配送项目（二次）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434136.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`eff2db891b4db46d309d3f4d3d2a88a1f404e26b2140b4e48412a6b82e683962`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_043c4aecbd4441a78f1a3edb

- 原始来源：[上海海关多智能体及场景应用建设开发服务采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434089.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`39cce56599d7f3ab46f5407702eb2df586e1a2c1487c6f80ff707d7b816a2e62`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_ea1b28d6c3894c6c9f32d7aa

- 原始来源：[上海海关多智能体及场景应用建设开发服务采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434089.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`39cce56599d7f3ab46f5407702eb2df586e1a2c1487c6f80ff707d7b816a2e62`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_ab4fda9c37754eb2bbd95e35

- 原始来源：[2026年国家级应急物资-陕西、四川激光测风雷达采购（第三次）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434178.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`5a0b922bb59f5d922a45ac2940e84b492da50142ae4a6040c3d9395e606e5f2e`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a6293e082c81450f9245c6bb

- 原始来源：[2026年国家级应急物资-陕西、四川激光测风雷达采购（第三次）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434178.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`5a0b922bb59f5d922a45ac2940e84b492da50142ae4a6040c3d9395e606e5f2e`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d69b50932d2d4d3fb80d4661

- 原始来源：[中山大学分析测试中心激光共聚焦显微镜采购项目（二）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434080.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`143a6f44c1a44887fd1ebdac0d823a0cfd99725b16fc9cb0d076be85273edbae`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_565692bffd7e4b92a4c3c18a

- 原始来源：[中山大学分析测试中心激光共聚焦显微镜采购项目（二）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434080.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`143a6f44c1a44887fd1ebdac0d823a0cfd99725b16fc9cb0d076be85273edbae`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_685d8ba8a5c44edfafcdc333

- 原始来源：[广东海事局2026-2027年海巡船艇船用燃油供应服务统一采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434055.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`0919e1ce4d374b5f56cb5c6d8ace52b95e2fae5b36984a21339d1729c628a907`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_95d40115d6c446809175d6b5

- 原始来源：[广东海事局2026-2027年海巡船艇船用燃油供应服务统一采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434055.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`0919e1ce4d374b5f56cb5c6d8ace52b95e2fae5b36984a21339d1729c628a907`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_e6476cc88d32487ab6723074

- 原始来源：[中山大学分析测试中心激光共聚焦显微镜采购项目（一）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434003.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`cf1ee279e653022a00f950bfd5b3985c5819e54a565477160b0ee139bf099a28`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_20d6572ce687416f8f55d696

- 原始来源：[中山大学分析测试中心激光共聚焦显微镜采购项目（一）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434003.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`cf1ee279e653022a00f950bfd5b3985c5819e54a565477160b0ee139bf099a28`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_c8847a01bb4b4434a490e75f

- 原始来源：[ZYCGR22011901智能疫苗和抗体筛选模块二期（自动化抗体生产工作站）采购项目（CLF0126GZ06ZC63）中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434009.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`b71c4713c76f76fd40ae509b146415bc5d7f9d451a5b77eb1988b84deafd7878`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a47e8a9f73c041bda39030cb

- 原始来源：[ZYCGR22011901智能疫苗和抗体筛选模块二期（自动化抗体生产工作站）采购项目（CLF0126GZ06ZC63）中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27434009.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`b71c4713c76f76fd40ae509b146415bc5d7f9d451a5b77eb1988b84deafd7878`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_6eea234215a7477e91440b8c

- 原始来源：[西北工业大学回油管油气两相流高精度测试技术试验系统中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433788.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2aa93fb4887a9a57d8abc199e3965626065068d44d3a7e13edc491a3bf2b1f3d`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_466b7a6d30104d6f9cdb9214

- 原始来源：[西北工业大学回油管油气两相流高精度测试技术试验系统中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433788.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`2aa93fb4887a9a57d8abc199e3965626065068d44d3a7e13edc491a3bf2b1f3d`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d65b667b4e864b5c80def2d2

- 原始来源：[中华人民共和国上海海关海关视觉大模型及场景应用智能体开发服务项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433739.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`ea60ac3fd4883ac8edf58f7e997c46bcfef5c69ff66d22cffe0c73201bfba23e`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_87799a6d7663402e90e2b247

- 原始来源：[中华人民共和国上海海关海关视觉大模型及场景应用智能体开发服务项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433739.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`ea60ac3fd4883ac8edf58f7e997c46bcfef5c69ff66d22cffe0c73201bfba23e`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_b0416a99ad764464ac500529

- 原始来源：[华中科技大学采购军山校区计算机实训教学及标准化考场设备项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433737.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e7605e1b70daf68b82133389dc00f1301f53db1697f19ce8dca357170d084c9d`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_8aec213147264ed6a6296fa6

- 原始来源：[华中科技大学采购军山校区计算机实训教学及标准化考场设备项目中标结果公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433737.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`e7605e1b70daf68b82133389dc00f1301f53db1697f19ce8dca357170d084c9d`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_92137dd811bd4922a58e7214

- 原始来源：[南京航空航天大学航空航天先进材料与结构多激光增材制造平台中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433686.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`34d5294bcd8a299607135187b62e7329adbde71caafba6320c2adf3bbb71beea`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a1dbf7542a0841cb8d5b739c

- 原始来源：[南京航空航天大学航空航天先进材料与结构多激光增材制造平台中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433686.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`34d5294bcd8a299607135187b62e7329adbde71caafba6320c2adf3bbb71beea`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_7b0aefbb805c4e659029be77

- 原始来源：[上海海关全自动超低温保存冰箱、全自动超低温存储系统、全自动血型分析仪采购项目（包件一、包件二）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433423.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`0b2761dfe61a221a4f5f07edbb7f2fa11ff75bab7fa5d0ed316294be46181048`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_19c8c729faee4a45a0997ccc

- 原始来源：[上海海关全自动超低温保存冰箱、全自动超低温存储系统、全自动血型分析仪采购项目（包件一、包件二）中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433423.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`0b2761dfe61a221a4f5f07edbb7f2fa11ff75bab7fa5d0ed316294be46181048`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_65e4fabe46244b368734b171

- 原始来源：[中国石油大学（北京）Elsevier Science Direct数据库采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433372.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`55470ba55cdd8c634ecdfa499609c8380b2c490140cfbf1e17ded50a42679439`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_f90d8066ee6844f382b3d8f6

- 原始来源：[中国石油大学（北京）Elsevier Science Direct数据库采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433372.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`55470ba55cdd8c634ecdfa499609c8380b2c490140cfbf1e17ded50a42679439`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d312390137324b798a89ab27

- 原始来源：[中国石油大学（北京）2026年外文电子资源采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433270.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`c4d16799fb6904dcfd839cab8e74fd3b29b6ed9c5280e3325a762b390566ab86`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_323ecaa880da4e519b2581e9

- 原始来源：[中国石油大学（北京）2026年外文电子资源采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433270.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`c4d16799fb6904dcfd839cab8e74fd3b29b6ed9c5280e3325a762b390566ab86`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_c66b7ae321a346469e305483

- 原始来源：[2026年公安部道路交通安全研究中心算力集群设备采购项目Ⅱ中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433463.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`77aca2e9dcfd21749d9e6592ec4fdfb1382f46f6bccadb29c593000a486568d1`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_f4a9a946a2134f87b56e52c4

- 原始来源：[2026年公安部道路交通安全研究中心算力集群设备采购项目Ⅱ中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433463.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`77aca2e9dcfd21749d9e6592ec4fdfb1382f46f6bccadb29c593000a486568d1`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_a64bb8b936a84f61b5c036a1

- 原始来源：[义乌市消防救援支队廿三里消防救援站一体化俱乐部改造项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433110.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`41c7035a71534454ce5cbe50371b4131164c7da2e4572e4b9bc627a0ff15b455`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_8524c4bec1bc408986ded22d

- 原始来源：[义乌市消防救援支队廿三里消防救援站一体化俱乐部改造项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433110.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`41c7035a71534454ce5cbe50371b4131164c7da2e4572e4b9bc627a0ff15b455`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_9399c25be4c548829ea5657a

- 原始来源：[中国人民银行浙江省分行中国人民银行丽水市分行扫描仪采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433958.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`19b416bc5516767c4c3c12a7bef933c66b491ee838fe072f06d69b4d1924884a`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_3aec5b2fd2644864a3b9e973

- 原始来源：[中国人民银行浙江省分行中国人民银行丽水市分行扫描仪采购项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433958.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`19b416bc5516767c4c3c12a7bef933c66b491ee838fe072f06d69b4d1924884a`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_6a8b95a1c4384c2191603313

- 原始来源：[广东省潮州市气象局办公旧址业务楼及大院物业管理服务项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27432963.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`6c3f3bef72a48c541412b5776e2c13732c94f88686fc8f0aa80cc8f87b0069a5`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_9b443798e2e14278b7457cd3

- 原始来源：[广东省潮州市气象局办公旧址业务楼及大院物业管理服务项目中标公告](http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27432963.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`6c3f3bef72a48c541412b5776e2c13732c94f88686fc8f0aa80cc8f87b0069a5`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：True。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_e9162ca75b1f4c8ca823a07f

- 原始来源：[财政部公布2026年政府采购代理机构检查名单_中国政府采购网](http://www.ccgp.gov.cn/news/202607/t20260715_26935390.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：2；正文 SHA256：`9ded4282e19b0c8ab4860b1d6a8e2ebf80ae8ce90c0bca0dcdfde8ee242be297`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_7e932fee108c404290302cca

- 原始来源：[广东将低空经济服务纳入政府购买服务范围_中国政府采购网](http://www.ccgp.gov.cn/gpsr/zhxx/df/202511/t20251114_25695352.htm)；企业：ccgp。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：2；正文 SHA256：`1035bf9eb060383517ac5e3fe251049491bb0cf2ae1d5ee67dcad3368314a77a`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_42477d1f5a67404fbc4b6ac0

- 原始来源：[联系我们-费勉科技（上海）股份有限公司](http://www.fermi-instruments.com/contact.html)；企业：费勉科技（上海）股份有限公司。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`11ccaabd837d05f0bad6eef1cccddf9191d35955ed763eb22ad4fb147a746537`。
- 证据问题：[]；新规则仅诊断：UNKNOWN；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_2e5fdbc554314c1b8baffb7b

- 原始来源：[AI产品及解决方案 - 神州数码集团](https://www.digitalchina.com/list-371-1.html)；企业：神州数码信息系统有限公司。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`84af9432e428ca8c26005b5324f25eaedc1623af8a0ef459b1d013369882167a`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_d49f7eeddd364962b7d684ae

- 原始来源：[AI产品及解决方案 - 神州数码集团](https://www.digitalchina.com/list-371-1.html)；企业：神州数码信息系统有限公司。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`84af9432e428ca8c26005b5324f25eaedc1623af8a0ef459b1d013369882167a`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_dbf784b1b55744a6a52d994b

- 原始来源：[数字化应用开发 - 服务 - 神州数码集团](https://www.digitalchina.com/product/details222.html)；企业：神州数码信息系统有限公司。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`5344494a2f6e509629278a8803b45f254d496c43defab46f0193133afe53338e`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 2 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

### sig_6a9d5c2429a84594990fd05b

- 原始来源：[数字化应用开发 - 服务 - 神州数码集团](https://www.digitalchina.com/product/details222.html)；企业：神州数码信息系统有限公司。
- 分类依据：Missing/blocked original version or evidence; semantic verdict unavailable；原版本快照：False；版本：1；正文 SHA256：`5344494a2f6e509629278a8803b45f254d496c43defab46f0193133afe53338e`。
- 证据问题：[]；新规则仅诊断：SUPPLY_CAPABILITY；历史标志：False。
- PainPoint：[]；OpportunityCandidate：[]；审批日志 1 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。

## 需要单独授权的历史修复步骤

本轮不执行修复。先由真实审核人确认两条偏移错误及 6 条 P1 的原版本证据；缺失快照只接受可信历史备份，不使用当前在线页面顶替。另立授权任务后备份正式库、限定 ID、修复版本与精确引用、检查下游依赖，记录逐行 before/after 和可回滚日志。恢复验证或联系就绪必须另经正式人工审批，不能因为本轮测试通过解除隔离。

R1 历史审计覆盖完成；真实性恢复/历史批准修正仍 BLOCKED。
