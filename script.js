document.addEventListener('DOMContentLoaded', () => {
    const passwordDisplay = document.getElementById('password-display');
    const typingStatus = document.getElementById('typing-status');
    const analysisPanel = document.getElementById('analysis-panel');
    const strengthBar = document.getElementById('strength-bar');
    const strengthText = document.getElementById('strength-text');
    const feedbackItems = document.getElementById('feedback-items');
    const leakInfo = document.getElementById('leak-info');
    const refreshButton = document.getElementById('refresh-button');

    // Function to update the password display and analysis
    const updatePasswordInfo = async () => {
        const response = await fetch('/get_typing_status');
        const data = await response.json();

        passwordDisplay.textContent = data.password || '...';
        typingStatus.textContent = data.finished ? 'Typing Complete!' : 'Point to type...';
        typingStatus.className = `typing-status ${data.finished ? 'complete' : 'active'}`;

        if (data.finished) {
            analysisPanel.classList.remove('hidden');
            analysisPanel.classList.add('visible');

            // Update strength meter
            const strengthLevels = {
                'Very Weak': { width: '20%', color: '#e74c3c' },
                'Weak': { width: '40%', color: '#e67e22' },
                'Moderate': { width: '60%', color: '#f1c40f' },
                'Strong': { width: '80%', color: '#2ecc71' },
                'Very Strong': { width: '100%', color: '#27ae60' }
            };
            const strength = strengthLevels[data.strength];
            strengthBar.style.width = strength.width;
            strengthBar.style.backgroundColor = strength.color;
            strengthText.textContent = `Strength: ${data.strength}`;

            // Update feedback
            feedbackItems.innerHTML = data.feedback.map(feedback => `
                <div class="feedback-item ${feedback.startsWith('Good') ? 'good' : 'bad'}">
                    ${feedback}
                </div>
            `).join('');

            // Update leak info
            if (data.leaked === null) {
                leakInfo.textContent = 'Unable to check password safety.';
                leakInfo.className = 'leak-info';
            } else if (data.leaked) {
                leakInfo.textContent = `Password leaked ${data.leak_count} times!`;
                leakInfo.className = 'leak-info compromised';
            } else {
                leakInfo.textContent = 'Password is safe!';
                leakInfo.className = 'leak-info safe';
            }

            refreshButton.classList.remove('hidden');
        }
    };

    // Refresh button functionality
    refreshButton.addEventListener('click', async () => {
        await fetch('/reset_typing', { method: 'POST' });
        location.reload();
    });

    // Poll for updates every second
    setInterval(updatePasswordInfo, 1000);
});