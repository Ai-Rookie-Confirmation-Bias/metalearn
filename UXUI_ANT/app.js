/**
 * MetaLearn Landing Page - Interactive Demo Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    
    /* 1. Interactive Demo: Sliding Logic */
    const tabs = document.querySelectorAll('.demo-tab');
    const slider = document.querySelector('.demo-slider');
    const btnNext = document.querySelector('.btn-slide-next');
    const btnPrev = document.querySelector('.btn-slide-prev');
    
    // Slide to a specific index (0: Learn, 1: Quiz)
    const slideTo = (index) => {
        // Update tabs
        tabs.forEach(t => t.classList.remove('active'));
        if(tabs[index]) tabs[index].classList.add('active');
        
        // Transform slider (0% or -50%)
        slider.style.transform = `translateX(-${index * 50}%)`;

        // Update height smoothly
        const viewport = document.querySelector('.demo-viewport');
        const panels = document.querySelectorAll('.demo-panel');
        if (viewport && panels[index]) {
            viewport.style.height = `${panels[index].scrollHeight}px`;
        }
    };

    // Initial height setup
    setTimeout(() => { slideTo(0); }, 50); // slight delay to ensure DOM is fully rendered for height calculation

    // Click on Tabs
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const index = parseInt(tab.getAttribute('data-index'));
            slideTo(index);
        });
    });

    // Click on "개념을 이해했어요 ->"
    if (btnNext) {
        btnNext.addEventListener('click', () => slideTo(1));
    }
    
    // Click on "다시 학습하기"
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            resetQuiz();
            slideTo(0);
        });
    }

    /* 2. Interactive Demo: Quiz Logic */
    const quizOptions = document.querySelectorAll('.quiz-option');
    const feedbackBox = document.querySelector('.quiz-feedback');
    const feedbackText = document.querySelector('.feedback-text');

    quizOptions.forEach(option => {
        option.addEventListener('click', () => {
            // Disable all options once clicked
            quizOptions.forEach(opt => opt.classList.add('disabled'));
            
            const isCorrect = option.getAttribute('data-correct') === 'true';
            
            if (isCorrect) {
                option.classList.add('correct');
                feedbackBox.classList.remove('hidden', 'error');
                feedbackBox.classList.add('success');
                feedbackText.innerHTML = "🎉 정답입니다! 객관적인 자기 파악이 바로 메타인지의 핵심입니다.";
            } else {
                option.classList.add('wrong');
                // Highlight the correct one as well
                document.querySelector('.quiz-option[data-correct="true"]').classList.add('correct');
                
                feedbackBox.classList.remove('hidden', 'success');
                feedbackBox.classList.add('error');
                feedbackText.innerHTML = "💡 아쉽습니다. 메타인지는 '자신이 모른다는 사실을 인지'하고 보완하는 과정과 관련이 깊습니다.";
            }

            // 피드백 박스가 나타나서 높이가 길어졌으므로, 뷰포트 높이를 다시 계산해서 부드럽게 늘려줌
            const viewport = document.querySelector('.demo-viewport');
            const quizPanel = document.querySelectorAll('.demo-panel')[1];
            if (viewport && quizPanel) {
                setTimeout(() => {
                    viewport.style.height = `${quizPanel.scrollHeight}px`;
                }, 10);
            }
        });
    });

    function resetQuiz() {
        quizOptions.forEach(opt => {
            opt.classList.remove('correct', 'wrong', 'disabled');
        });
        feedbackBox.classList.add('hidden');
    }

});
