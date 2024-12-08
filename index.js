const toggle = document.getElementById('pricingToggle');
const annualPrices = document.querySelectorAll('.annual-price');
const monthlyPrices = document.querySelectorAll('.monthly-price');

toggle.addEventListener('change', function() {
    if (this.checked) {
        annualPrices.forEach(price => price.style.display = 'none');
        monthlyPrices.forEach(price => price.style.display = 'block');
    } else {
        annualPrices.forEach(price => price.style.display = 'block');
        monthlyPrices.forEach(price => price.style.display = 'none');
    }
});