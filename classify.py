# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------------#
#  Name:           classify.py                                                        #
#  Description:    single-label classification based on linear SVM                    #
#-------------------------------------------------------------------------------------#
from sklearn import metrics, preprocessing, svm, decomposition
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from scipy.sparse.csr import csr_matrix
import numpy as np
import pickle
import random
import argparse
import time


class MyCountVectorizer(CountVectorizer):
    """
    Extract the last column of the input matrix (which is app description) and
    simply pass it to CountVectorizer.

    Parameters
    ----------
    (identical to the parameters of CountVectorizer)
    """

    def __init__(self, input='content', encoding='utf-8', decode_error='strict',
                 strip_accents=None, lowercase=True, preprocessor=None, tokenizer=None,
                 stop_words=None, token_pattern=r'(?u)\b\w\w +\b', ngram_range=(1, 1),
                 analyzer='word', max_df=1.0, min_df=1, max_features=None, vocabulary=None,
                 binary=False, dtype=np.int64):

        return super().__init__(input=input, encoding=encoding, decode_error=decode_error,
                                strip_accents=strip_accents, lowercase=lowercase, preprocessor=preprocessor,
                                tokenizer=tokenizer, stop_words=stop_words, token_pattern=token_pattern,
                                ngram_range=ngram_range, analyzer=analyzer, max_df=max_df, min_df=min_df,
                                max_features=max_features, vocabulary=vocabulary, binary=binary, dtype=dtype)

    def fit(self, x, *args, **kwargs):
        return super().fit(x[:, -1].tolist(), *args, **kwargs)

    def fit_transform(self, x, *args, **kwargs):
        return super().fit_transform(x[:, -1].tolist(), *args, **kwargs)

    def transform(self, x, *args, **kwargs):
        return super().transform(x[:, -1].tolist(), *args, **kwargs)


class MyTfidfVectorizer(TfidfVectorizer):
    """
    Extract the last column of the input matrix (which is app description) and
    simply pass it to TfidfVectorizer.

    Parameters
    ----------
    (identical to the parameters of TfidfVectorizer)
    """

    def __init__(self, input='content', encoding='utf-8', decode_error='strict',
                 strip_accents=None, lowercase=True, preprocessor=None, tokenizer=None,
                 analyzer='word', stop_words=None, token_pattern=r'(?u)\b\w\w+\b',
                 ngram_range=(1, 1), max_df=1.0, min_df=1, max_features=None,
                 vocabulary=None, binary=False, dtype=np.int64, norm='l2', use_idf=True,
                 smooth_idf=True, sublinear_tf=False):

        return super().__init__(input=input, encoding=encoding, decode_error=decode_error,
                                strip_accents=strip_accents, lowercase=lowercase, preprocessor=preprocessor,
                                tokenizer=tokenizer, analyzer=analyzer, stop_words=stop_words,
                                token_pattern=token_pattern, ngram_range=ngram_range, max_df=max_df,
                                min_df=min_df, max_features=max_features, vocabulary=vocabulary,
                                binary=binary, dtype=dtype, norm=norm, use_idf=use_idf,
                                smooth_idf=smooth_idf, sublinear_tf=sublinear_tf)

    def fit(self, x, *args, **kwargs):
        return super().fit(x[:, -1].tolist(), *args, **kwargs)

    def fit_transform(self, x, *args, **kwargs):
        return super().fit_transform(x[:, -1].tolist(), *args, **kwargs)

    def transform(self, x, *args, **kwargs):
        return super().transform(x[:, -1].tolist(), *args, **kwargs)


class MyScaler(preprocessing.StandardScaler):
    """
    Standardize features by removing the mean and scaling to unit variance. Both
    fit_tranform and tranform method return sparse matrix in csr format.

    Parameters
    ----------
    (null)

    Attributes
    ----------
    mean_: numpy.array, shape (n_features)
        the mean value for each features in the input matrix
    std_: numpy.array, shape (n_features)
        the standard deviation for each features in the input matrix
    """

    def __init__(self, identical=False):
        self.mean_ = None
        self.std_ = None
        self.epsilon = 0.000001
        self.identical = identical

    def fit(self, X, y=None):
        X = X[:, :-1].astype('float64')
        self.mean_ = np.mean(X, axis=0) if not self.identical else 0
        self.std_ = np.std(X, axis=0) if not self.identical else 1
        return self

    def fit_tranform(self, X, y=None):
        X = X[:, :-1].astype('float64')
        self.mean_ = np.mean(X, axis=0) if not self.identical else 0
        self.std_ = np.std(X, axis=0) if not self.identical else 1
        res = (X - self.mean_) / (self.std_ + self.epsilon)
        return csr_matrix(res)

    def transform(self, X, y=None):
        X = X[:, :-1].astype('float64')
        res = (X - self.mean_) / (self.std_ + self.epsilon)
        return csr_matrix(res)


def main(args):
    """
    Grid-search over different parameters for a linear SVM classifier using
    a 3-fold cross valiadation.

    args: argparse.Namespace object

    Returns: None
    """

    # load dataset
    with open(args.infile, 'rb') as fin:
        x_train, y_train, x_test, y_test = pickle.load(fin)

    y_train = y_train.astype('int64')
    y_test = y_test.astype('int64')

    random_index = list(range(len(x_train)))
    random.shuffle(random_index)
    x_train = np.array(x_train[random_index])
    y_train = np.array(y_train[random_index])

    # y_train = y_train.astype(bool).astype(int)
    # y_test = y_test.astype(bool).astype(int)

    # combined different features
    feature_extractors = [
        # ('general', MyScaler(False)),
        # ('wordcount', MyCountVectorizer(ngram_range=(1, 1), stop_words='english')),
        ('tfidf', MyTfidfVectorizer(stop_words='english')),
    ]
    combined_feature = FeatureUnion(feature_extractors)

    estimators = [('feature', combined_feature),
                  ('clf', svm.LinearSVC(C=0.3))]
    pipeline = Pipeline(estimators)

    # pipeline.fit(x_train, y_train)
    # print(pipeline.score(x_test, y_test))

    # parameters to search
    param_grid = [
        {
            'clf': [MultinomialNB()],
            'clf__alpha': [10, 1.0, 0.1, 0.01],
        },
        {
            'clf': [svm.LinearSVC()],
            'clf__C': [3, 1, 0.3, 0.1],
        },
    ]

    # start training
    t0 = time.time()
    grid = GridSearchCV(pipeline, param_grid=param_grid, verbose=4, n_jobs=4)
    grid.fit(x_train, y_train)

    print()
    print('done in %.2f seconds' % (time.time() - t0))
    print()
    print('train accuracy: %.2f%%' % (100 * grid.score(x_train, y_train)))
    print('test accuracy: %.2f%%' % (100 * grid.score(x_test, y_test)))
    print()
    print('the best parameters are:', grid.best_params_)
    print()
    print('confusion matrix:')
    print(metrics.confusion_matrix(y_test, grid.predict(x_test)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('infile',
                        help='file path of the dataset')
    args = parser.parse_args()
    main(args)
