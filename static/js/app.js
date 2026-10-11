const input = document.querySelector('#image-input');
const dropZone = document.querySelector('#drop-zone');
const form = document.querySelector('#upload-form');

if (input && dropZone && form) {
  const preview = document.querySelector('#image-preview');
  const previewImage = document.querySelector('#preview-image');
  const previewName = document.querySelector('#preview-name');
  const submitButton = document.querySelector('#submit-button');
  const error = document.querySelector('#file-error');
  const progress = document.querySelector('#analysis-progress');
  const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);
  const maxBytes = 10 * 1024 * 1024;
  let previewUrl;

  const clearError = () => {
    error.hidden = true;
    error.textContent = '';
  };

  const resetFile = () => {
    input.value = '';
    submitButton.disabled = true;
    preview.hidden = true;
    dropZone.hidden = false;
    previewImage.removeAttribute('src');
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = undefined;
  };

  const selectFile = (file) => {
    clearError();
    if (!file) return;
    if (!allowedTypes.has(file.type)) {
      error.textContent = 'Pilih gambar JPEG, PNG, atau WEBP.';
      error.hidden = false;
      resetFile();
      return;
    }
    if (file.size > maxBytes) {
      error.textContent = 'Ukuran gambar melebihi batas 10 MB.';
      error.hidden = false;
      resetFile();
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    previewImage.src = previewUrl;
    previewName.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
    dropZone.hidden = true;
    preview.hidden = false;
    submitButton.disabled = false;
  };

  input.addEventListener('change', () => selectFile(input.files[0]));
  document.querySelector('#remove-file').addEventListener('click', () => {
    clearError();
    resetFile();
  });
  dropZone.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      input.click();
    }
  });
  ['dragenter', 'dragover'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add('dragging');
  }));
  ['dragleave', 'drop'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove('dragging');
  }));
  dropZone.addEventListener('drop', (event) => {
    const [file] = event.dataTransfer.files;
    if (file) {
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      selectFile(file);
    }
  });
  form.addEventListener('submit', (event) => {
    if (!input.files.length || submitButton.disabled) {
      event.preventDefault();
      return;
    }
    submitButton.disabled = true;
    submitButton.querySelector('span:first-child').textContent = 'Memeriksa…';
    progress.hidden = false;
  });
}

document.querySelectorAll('form[data-confirm]').forEach((formElement) => {
  formElement.addEventListener('submit', (event) => {
    if (!window.confirm(formElement.dataset.confirm)) event.preventDefault();
  });
});
